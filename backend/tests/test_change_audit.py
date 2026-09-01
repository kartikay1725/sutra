import uuid
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.session import Base, get_db
from app.main import app
from app.models.actor import Actor
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.change_review import ChangeReview
from app.models.repository import Repository
from app.models.user import User
from app.models.agent import Agent
from app.services.change_service import ChangeService
from app.services.change_policy_service import PolicyDecision, ChangePolicyService


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client(db: Session):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def make_user(db: Session) -> User:
    username = f"user-{uuid.uuid4().hex[:8]}"
    user = User(
        id=str(uuid.uuid4()),
        username=username,
        email=f"{username}@example.com",
        password_hash="test-hash",
    )
    db.add(user)
    db.flush()
    return user


def make_repository(db: Session, owner_id: str) -> Repository:
    repository_id = str(uuid.uuid4())
    repository = Repository(
        id=repository_id,
        owner_id=owner_id,
        name=f"repo-{repository_id[:8]}",
        slug=f"repo-{repository_id[:8]}",
        description="Test repo",
        visibility="private",
        default_branch="main",
        storage_key=f"repo-{repository_id[:8]}.git",
    )
    db.add(repository)
    db.flush()
    return repository


def make_actor(db: Session, owner_id: str) -> Actor:
    actor = Actor(
        id=str(uuid.uuid4()),
        type="human",
        name=f"actor-{uuid.uuid4().hex[:8]}",
        owner_id=owner_id,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    db.add(actor)
    db.flush()
    return actor


def make_agent(db: Session, owner_id: str) -> Agent:
    agent = Agent(
        id=str(uuid.uuid4()),
        owner_id=owner_id,
        name="Test Agent",
        token_hash="unused",
        token_prefix="sutra_agent_test",
        status="active",
        is_active=True,
    )
    db.add(agent)
    db.flush()
    return agent


def auth_headers(user: User):
    token = create_access_token(user.id)
    return {
        "Authorization": f"Bearer {token}",
    }


# ---------------------------------------------------------------------------
# Audit and State Transition Tests
# ---------------------------------------------------------------------------

def test_change_creation_logs_event(client: TestClient, db: Session):
    user = make_user(db)
    repo = make_repository(db, user.id)
    db.commit()

    response = client.post(
        "/v1/changes",
        json={
            "repository_id": repo.id,
            "intent": "Manual test intent",
            "risk_level": "low",
        },
        headers=auth_headers(user),
    )
    assert response.status_code == 201
    change_id = response.json()["id"]

    events = db.scalars(
        select(ChangeEvent).where(ChangeEvent.change_id == change_id)
    ).all()
    assert len(events) == 1
    assert events[0].event_type == "change.created"
    assert events[0].from_status is None
    assert events[0].to_status == "proposed"
    meta = json.loads(events[0].metadata_json)
    assert meta["intent"] == "Manual test intent"


def test_agent_change_creation_logs_event(client: TestClient, db: Session):
    from app.api.agent_dependencies import get_current_agent
    user = make_user(db)
    agent = make_agent(db, user.id)
    repo = make_repository(db, user.id)

    actor = Actor(
        id=agent.id,
        type="agent",
        name=agent.name,
        owner_id=user.id,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    db.add(actor)
    db.commit()

    app.dependency_overrides[get_current_agent] = lambda: agent

    response = client.post(
        "/v1/changes/agent",
        json={
            "repository_id": repo.id,
            "intent": "Agent test intent",
            "risk_level": "low",
        },
        headers={"Authorization": "Bearer agent-token"},
    )
    assert response.status_code == 201
    change_id = response.json()["id"]

    events = db.scalars(
        select(ChangeEvent).where(ChangeEvent.change_id == change_id)
    ).all()
    assert len(events) == 1
    assert events[0].event_type == "change.created"
    meta = json.loads(events[0].metadata_json)
    assert meta["intent"] == "Agent test intent"

    app.dependency_overrides.pop(get_current_agent, None)


def test_invalid_status_transition_rejected(db: Session):
    user = make_user(db)
    repo = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Test",
        status="recorded",
    )
    db.add(change)
    db.commit()

    service = ChangeService(db)
    with pytest.raises(ValueError, match="Invalid status transition"):
        service.transition_change(
            change=change,
            new_status="proposed",
            actor_id=actor.id,
            event_type="test.invalid",
        )


def test_recorded_change_cannot_transition_back_to_proposed(db: Session):
    user = make_user(db)
    repo = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Test",
        status="recorded",
    )
    db.add(change)
    db.commit()

    service = ChangeService(db)
    with pytest.raises(ValueError, match="Invalid status transition"):
        service.transition_change(
            change=change,
            new_status="proposed",
            actor_id=actor.id,
            event_type="rollback",
        )


def test_blocked_change_cannot_be_finalized(client: TestClient, db: Session, monkeypatch):
    user = make_user(db)
    repo = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Test",
        status="blocked",
    )
    db.add(change)
    db.commit()

    response = client.post(
        f"/v1/changes/{change.id}/finalize",
        headers=auth_headers(user),
    )
    assert response.status_code == 409
    assert "Only proposed changes can be finalized" in response.json()["detail"]


def test_review_request_creates_audit_event(client: TestClient, db: Session, monkeypatch):
    user = make_user(db)
    repo = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Test",
        status="proposed",
    )
    db.add(change)
    db.commit()

    monkeypatch.setattr(
        ChangePolicyService,
        "evaluate",
        lambda self, change: PolicyDecision(
            decision="review",
            reason="Requires review",
            reasons=[],
            conflict_level="none",
            related_change_ids=[],
            dependency_count=0,
            capabilities=[],
        ),
    )

    response = client.post(
        f"/v1/changes/{change.id}/reviews",
        json={"reason": "Please look at this"},
        headers=auth_headers(user),
    )
    assert response.status_code == 201
    review_id = response.json()["id"]

    events = db.scalars(
        select(ChangeEvent)
        .where(ChangeEvent.change_id == change.id)
        .where(ChangeEvent.event_type == "change.review_requested")
    ).all()
    assert len(events) == 1
    meta = json.loads(events[0].metadata_json)
    assert meta["review_id"] == review_id
    assert meta["requested_by"] == user.id


def test_review_approval_creates_audit_event(client: TestClient, db: Session, monkeypatch):
    user = make_user(db)
    reviewer = make_user(db)
    repo = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Test",
        status="proposed",
    )
    review = ChangeReview(
        change_id=change.id,
        requested_by=user.id,
        status="pending",
        reason="Check",
    )
    db.add(change)
    db.add(review)
    db.commit()

    monkeypatch.setattr(
        ChangePolicyService,
        "evaluate",
        lambda self, change: PolicyDecision(
            decision="review",
            reason="Requires review",
            reasons=[],
            conflict_level="none",
            related_change_ids=[],
            dependency_count=0,
            capabilities=[],
        ),
    )

    response = client.post(
        f"/v1/changes/{change.id}/reviews/{review.id}/approve",
        json={"reason": "LGTM!"},
        headers=auth_headers(reviewer),
    )
    assert response.status_code == 200

    events = db.scalars(
        select(ChangeEvent)
        .where(ChangeEvent.change_id == change.id)
        .where(ChangeEvent.event_type == "change.review_approved")
    ).all()
    assert len(events) == 1
    meta = json.loads(events[0].metadata_json)
    assert meta["reviewer_id"] == reviewer.id
    assert meta["review_id"] == review.id
    assert meta["reason"] == "LGTM!"


def test_review_rejection_creates_audit_event(client: TestClient, db: Session, monkeypatch):
    user = make_user(db)
    reviewer = make_user(db)
    repo = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Test",
        status="proposed",
    )
    review = ChangeReview(
        change_id=change.id,
        requested_by=user.id,
        status="pending",
        reason="Check",
    )
    db.add(change)
    db.add(review)
    db.commit()

    response = client.post(
        f"/v1/changes/{change.id}/reviews/{review.id}/reject",
        json={"reason": "Needs improvements"},
        headers=auth_headers(reviewer),
    )
    assert response.status_code == 200

    events = db.scalars(
        select(ChangeEvent)
        .where(ChangeEvent.change_id == change.id)
        .where(ChangeEvent.event_type == "change.review_rejected")
    ).all()
    assert len(events) == 1
    meta = json.loads(events[0].metadata_json)
    assert meta["reviewer_id"] == reviewer.id
    assert meta["review_id"] == review.id
    assert meta["reason"] == "Needs improvements"


def test_policy_evaluation_outcome_recorded(client: TestClient, db: Session, monkeypatch):
    user = make_user(db)
    repo = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Test",
        status="proposed",
    )
    db.add(change)
    db.commit()

    monkeypatch.setattr(
        ChangePolicyService,
        "evaluate",
        lambda self, change: PolicyDecision(
            decision="allow",
            reason="Clean low risk",
            reasons=[],
            conflict_level="none",
            related_change_ids=[],
            dependency_count=2,
            capabilities=[],
        ),
    )

    response = client.post(
        f"/v1/changes/{change.id}/finalize",
        headers=auth_headers(user),
    )
    assert response.status_code == 200

    events = db.scalars(
        select(ChangeEvent)
        .where(ChangeEvent.change_id == change.id)
        .where(ChangeEvent.event_type == "change.policy_evaluated")
    ).all()
    assert len(events) == 1
    meta = json.loads(events[0].metadata_json)
    assert meta["decision"] == "allow"
    assert meta["dependency_count"] == 2


def test_events_immutable_through_api(client: TestClient, db: Session):
    user = make_user(db)
    repo = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Test",
        status="proposed",
    )
    db.add(change)
    db.commit()

    # Attempt POST/PUT/DELETE directly on events endpoint
    response = client.post(
        f"/v1/changes/{change.id}/events",
        headers=auth_headers(user),
    )
    assert response.status_code == 405  # Method Not Allowed

    response = client.delete(
        f"/v1/changes/{change.id}/events",
        headers=auth_headers(user),
    )
    assert response.status_code == 405  # Method Not Allowed


def test_event_ordering_is_deterministic(client: TestClient, db: Session, monkeypatch):
    user = make_user(db)
    repo = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Test",
        status="proposed",
    )
    db.add(change)
    db.commit()

    service = ChangeService(db)
    service.transition_change(change, "proposed", actor.id, "change.created")
    service.transition_change(change, "proposed", actor.id, "event_b")
    service.transition_change(change, "proposed", actor.id, "event_c")
    db.commit()

    response = client.get(
        f"/v1/changes/{change.id}/events",
        headers=auth_headers(user),
    )
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 3
    assert events[0]["event_type"] == "change.created"
    assert events[1]["event_type"] == "event_b"
    assert events[2]["event_type"] == "event_c"


def test_audit_history_survives_subsequent_requests(client: TestClient, db: Session):
    user = make_user(db)
    repo = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Test",
        status="proposed",
    )
    db.add(change)
    db.commit()

    service = ChangeService(db)
    service.transition_change(change, "proposed", actor.id, "change.created")
    db.commit()

    # Query events
    response = client.get(
        f"/v1/changes/{change.id}/events",
        headers=auth_headers(user),
    )
    assert len(response.json()) == 1

    # Add another event and verify it survives
    service.transition_change(change, "proposed", actor.id, "another_event")
    db.commit()

    response = client.get(
        f"/v1/changes/{change.id}/events",
        headers=auth_headers(user),
    )
    assert len(response.json()) == 2


def test_agent_push_blocked_logs_nothing_due_to_rollback(db: Session, monkeypatch):
    user = make_user(db)
    agent = make_agent(db, user.id)
    actor = Actor(
        id=agent.id,
        type="agent",
        name=agent.name,
        owner_id=user.id,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    repo = make_repository(db, user.id)
    db.add(actor)
    db.commit()

    monkeypatch.setattr(
        ChangePolicyService,
        "evaluate",
        lambda self, change: PolicyDecision(
            decision="block",
            reason="Blocked push",
            reasons=[],
            conflict_level="none",
            related_change_ids=[],
            dependency_count=0,
            capabilities=[],
        ),
    )

    service = ChangeService(db)
    monkeypatch.setattr(service, "resolve_commit", lambda repo, commit: commit)
    monkeypatch.setattr(service, "_classify_ref_update", lambda repo, b, res: "update")
    monkeypatch.setattr(service, "get_changed_files", lambda repo, b, res: [])

    with pytest.raises(ValueError, match="Change blocked by SUTRA policy"):
        service.record_agent_push(
            repository=repo,
            actor=actor,
            base_commit="a" * 40,
            resulting_commit="b" * 40,
            intent="Critical push",
            risk_level="critical",
            metadata_json='{"ref": "refs/heads/main"}',
        )

    # Verify no ChangeEvent is persisted in DB for the rolled-back push
    events = db.query(ChangeEvent).all()
    assert len(events) == 0


def test_agent_push_under_review_logs_created_and_evaluated(db: Session, monkeypatch):
    user = make_user(db)
    agent = make_agent(db, user.id)
    actor = Actor(
        id=agent.id,
        type="agent",
        name=agent.name,
        owner_id=user.id,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    repo = make_repository(db, user.id)
    db.add(actor)
    db.commit()

    monkeypatch.setattr(
        ChangePolicyService,
        "evaluate",
        lambda self, change: PolicyDecision(
            decision="review",
            reason="Medium risk",
            reasons=[],
            conflict_level="none",
            related_change_ids=[],
            dependency_count=0,
            capabilities=[],
        ),
    )

    service = ChangeService(db)
    monkeypatch.setattr(service, "resolve_commit", lambda repo, commit: commit)
    monkeypatch.setattr(service, "_classify_ref_update", lambda repo, b, res: "update")
    monkeypatch.setattr(service, "get_changed_files", lambda repo, b, res: [])

    change = service.record_agent_push(
        repository=repo,
        actor=actor,
        base_commit="a" * 40,
        resulting_commit="b" * 40,
        intent="Medium push",
        risk_level="medium",
        metadata_json='{"ref": "refs/heads/main"}',
    )

    assert change.status == "proposed"

    events = db.query(ChangeEvent).filter(ChangeEvent.change_id == change.id).all()
    assert len(events) == 2
    assert events[0].event_type == "change.created"
    assert events[1].event_type == "change.policy_evaluated"


def test_agent_push_allow_logs_created_evaluated_and_finalized(db: Session, monkeypatch):
    user = make_user(db)
    agent = make_agent(db, user.id)
    actor = Actor(
        id=agent.id,
        type="agent",
        name=agent.name,
        owner_id=user.id,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    repo = make_repository(db, user.id)
    db.add(actor)
    db.commit()

    monkeypatch.setattr(
        ChangePolicyService,
        "evaluate",
        lambda self, change: PolicyDecision(
            decision="allow",
            reason="Low risk",
            reasons=[],
            conflict_level="none",
            related_change_ids=[],
            dependency_count=0,
            capabilities=[],
        ),
    )

    service = ChangeService(db)
    monkeypatch.setattr(service, "resolve_commit", lambda repo, commit: commit)
    monkeypatch.setattr(service, "_classify_ref_update", lambda repo, b, res: "update")
    monkeypatch.setattr(service, "get_changed_files", lambda repo, b, res: [])

    change = service.record_agent_push(
        repository=repo,
        actor=actor,
        base_commit="a" * 40,
        resulting_commit="b" * 40,
        intent="Low risk push",
        risk_level="low",
        metadata_json='{"ref": "refs/heads/main"}',
    )

    assert change.status == "recorded"

    events = db.query(ChangeEvent).filter(ChangeEvent.change_id == change.id).all()
    assert len(events) == 3
    assert events[0].event_type == "change.created"
    assert events[1].event_type == "change.policy_evaluated"
    assert events[2].event_type == "change.finalized"
