import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.session import Base, get_db
from app.main import app
from app.models.actor import Actor
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.repository import Repository
from app.models.user import User
from app.models.agent import Agent
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


def make_user(
    db: Session,
    user_id: str | None = None,
    username: str | None = None,
) -> User:
    user_id = user_id or str(uuid.uuid4())
    username = username or f"user-{uuid.uuid4().hex[:8]}"

    user = User(
        id=user_id,
        username=username,
        email=f"{username}@example.com",
        password_hash="test-password-hash",
    )

    db.add(user)
    db.flush()

    return user


def make_repository(
    db: Session,
    owner_id: str,
) -> Repository:
    repository_id = f"repo-{uuid.uuid4().hex[:8]}"

    repository = Repository(
        id=repository_id,
        owner_id=owner_id,
        name=repository_id,
        slug=repository_id.lower(),
        description="Test repository",
        visibility="private",
        default_branch="main",
        storage_key=f"{repository_id}.git",
    )

    db.add(repository)
    db.flush()

    return repository


def make_actor(
    db: Session,
    owner_id: str,
    actor_id: str | None = None,
) -> Actor:
    actor_id = actor_id or str(uuid.uuid4())
    actor = Actor(
        id=actor_id,
        type="agent",
        name=f"agent-{uuid.uuid4().hex[:8]}",
        owner_id=owner_id,
        capabilities='["repository.read", "repository.write", "change.create" , "change.commit"]',
    )

    db.add(actor)
    db.flush()

    return actor


def make_change(
    db: Session,
    repository_id: str,
    actor_id: str,
    risk_level: str = "low",
    status: str = "proposed",
) -> Change:
    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repository_id,
        actor_id=actor_id,
        intent="Test change",
        base_commit="a" * 40,
        resulting_commit="b" * 40,
        status=status,
        risk_level=risk_level,
        metadata_json="{}",
    )

    db.add(change)
    db.flush()

    return change


def auth_headers(user: User):
    token = create_access_token(user.id)
    return {
        "Authorization": f"Bearer {token}",
    }


def make_agent(db, owner_id, agent_id="agent-1"):
    agent = Agent(
        id=agent_id,
        owner_id=owner_id,
        name="Policy Test Agent",
        description="API policy test agent",
        provider="test",
        model="policy-test",
        token_hash="unused-in-overridden-auth",
        token_prefix="sutra_agent_test",
        status="active",
        is_active=True,
    )
    db.add(agent)
    db.flush()
    return agent


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_low_risk_allow_recorded(client: TestClient, db: Session, monkeypatch):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = make_change(db, repository.id, actor.id, risk_level="low")
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

    response = client.post(
        f"/v1/changes/{change.id}/finalize",
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "recorded"


def test_medium_risk_review_not_recorded(client: TestClient, db: Session, monkeypatch):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = make_change(db, repository.id, actor.id, risk_level="medium")
    db.commit()

    monkeypatch.setattr(
        ChangePolicyService,
        "evaluate",
        lambda self, change: PolicyDecision(
            decision="review",
            reason="Medium risk requires review",
            reasons=["Medium risk"],
            conflict_level="none",
            related_change_ids=[],
            dependency_count=0,
            capabilities=[],
        ),
    )

    response = client.post(
        f"/v1/changes/{change.id}/finalize",
        headers=auth_headers(user),
    )

    assert response.status_code == 409
    assert "requires an approved review" in response.json()["detail"]


def test_high_risk_review_not_recorded(client: TestClient, db: Session, monkeypatch):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = make_change(db, repository.id, actor.id, risk_level="high")
    db.commit()

    monkeypatch.setattr(
        ChangePolicyService,
        "evaluate",
        lambda self, change: PolicyDecision(
            decision="review",
            reason="High risk requires review",
            reasons=["High risk"],
            conflict_level="none",
            related_change_ids=[],
            dependency_count=0,
            capabilities=[],
        ),
    )

    response = client.post(
        f"/v1/changes/{change.id}/finalize",
        headers=auth_headers(user),
    )

    assert response.status_code == 409
    assert "requires an approved review" in response.json()["detail"]


def test_critical_block_rejected(client: TestClient, db: Session, monkeypatch):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = make_change(db, repository.id, actor.id, risk_level="critical")
    db.commit()

    monkeypatch.setattr(
        ChangePolicyService,
        "evaluate",
        lambda self, change: PolicyDecision(
            decision="block",
            reason="Critical changes are blocked",
            reasons=["Critical risk"],
            conflict_level="none",
            related_change_ids=[],
            dependency_count=0,
            capabilities=[],
        ),
    )

    response = client.post(
        f"/v1/changes/{change.id}/finalize",
        headers=auth_headers(user),
    )

    assert response.status_code == 409
    assert "blocked by SUTRA policy" in response.json()["detail"]


def test_review_pending_rejected(client: TestClient, db: Session, monkeypatch):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = make_change(db, repository.id, actor.id, risk_level="medium")

    # Create pending review
    review = ChangeReview(
        change_id=change.id,
        requested_by=user.id,
        status="pending",
        reason="Please check",
    )
    db.add(review)
    db.commit()

    monkeypatch.setattr(
        ChangePolicyService,
        "evaluate",
        lambda self, change: PolicyDecision(
            decision="review",
            reason="Medium risk",
            reasons=["Medium risk"],
            conflict_level="none",
            related_change_ids=[],
            dependency_count=0,
            capabilities=[],
        ),
    )

    response = client.post(
        f"/v1/changes/{change.id}/finalize",
        headers=auth_headers(user),
    )

    assert response.status_code == 409
    assert "requires an approved review" in response.json()["detail"]


def test_review_rejected_rejected(client: TestClient, db: Session, monkeypatch):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = make_change(db, repository.id, actor.id, risk_level="medium")

    reviewer = make_user(db)
    # Create rejected review
    review = ChangeReview(
        change_id=change.id,
        requested_by=user.id,
        reviewer_id=reviewer.id,
        status="rejected",
        reason="No way",
    )
    db.add(review)
    db.commit()

    monkeypatch.setattr(
        ChangePolicyService,
        "evaluate",
        lambda self, change: PolicyDecision(
            decision="review",
            reason="Medium risk",
            reasons=["Medium risk"],
            conflict_level="none",
            related_change_ids=[],
            dependency_count=0,
            capabilities=[],
        ),
    )

    response = client.post(
        f"/v1/changes/{change.id}/finalize",
        headers=auth_headers(user),
    )

    assert response.status_code == 409
    assert "requires an approved review" in response.json()["detail"]


def test_review_approved_recorded(client: TestClient, db: Session, monkeypatch):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = make_change(db, repository.id, actor.id, risk_level="medium")

    reviewer = make_user(db)
    # Create approved review
    review = ChangeReview(
        change_id=change.id,
        requested_by=user.id,
        reviewer_id=reviewer.id,
        status="approved",
        reason="Approved!",
    )
    db.add(review)
    db.commit()

    monkeypatch.setattr(
        ChangePolicyService,
        "evaluate",
        lambda self, change: PolicyDecision(
            decision="review",
            reason="Medium risk",
            reasons=["Medium risk"],
            conflict_level="none",
            related_change_ids=[],
            dependency_count=0,
            capabilities=[],
        ),
    )

    response = client.post(
        f"/v1/changes/{change.id}/finalize",
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "recorded"


def test_agent_commit_cannot_bypass_review(client: TestClient, db: Session, monkeypatch):
    from app.api.agent_dependencies import get_current_agent

    user = make_user(db)
    agent = make_agent(db, owner_id=user.id)
    actor = make_actor(db, user.id, actor_id=agent.id)
    repository = make_repository(db, user.id)
    change = make_change(db, repository.id, actor.id, risk_level="medium")
    db.commit()

    app.dependency_overrides[get_current_agent] = lambda: agent

    monkeypatch.setattr(
        ChangePolicyService,
        "evaluate",
        lambda self, change: PolicyDecision(
            decision="review",
            reason="Medium risk requires review",
            reasons=["Medium risk"],
            conflict_level="none",
            related_change_ids=[],
            dependency_count=0,
            capabilities=[],
        ),
    )

    monkeypatch.setattr("app.services.change_service.ChangeService.resolve_commit", lambda self, repo, commit: commit)
    monkeypatch.setattr("app.services.change_service.ChangeService.verify_ancestor", lambda self, repo, b, res: None)
    monkeypatch.setattr("app.services.change_service.ChangeService.get_changed_files", lambda self, repo, b, res: [])

    response = client.post(
        f"/v1/changes/{change.id}/agent-commit",
        json={
            "resulting_commit": "b" * 40,
        },
        headers={"Authorization": "Bearer test-agent-token"},
    )

    # Agent commit attaches evidence (200 OK) but leaves change in 'proposed' state pending review
    assert response.status_code == 200
    db.refresh(change)
    assert change.status == "proposed"
    assert change.resulting_commit == "b" * 40

    # Finalization must fail without an approved review
    from app.services.change_service import ChangeService
    with pytest.raises(ValueError, match="requires an approved review"):
        ChangeService(db).finalize_change(change)

    app.dependency_overrides.pop(get_current_agent, None)


def test_agent_push_cannot_bypass_block(client: TestClient, db: Session, monkeypatch):
    from app.services.change_service import ChangeService

    user = make_user(db)
    agent = make_agent(db, owner_id=user.id)
    actor = make_actor(db, user.id, actor_id=agent.id)
    repository = make_repository(db, user.id)
    db.commit()

    monkeypatch.setattr(
        ChangePolicyService,
        "evaluate",
        lambda self, change: PolicyDecision(
            decision="block",
            reason="Critical-risk changes are blocked",
            reasons=["Critical risk"],
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
            repository=repository,
            actor=actor,
            base_commit="a" * 40,
            resulting_commit="b" * 40,
            intent="Git push critical change",
            risk_level="critical",
            metadata_json='{"ref": "refs/heads/main"}',
        )


def test_agent_push_under_review_remains_proposed(client: TestClient, db: Session, monkeypatch):
    from app.services.change_service import ChangeService

    user = make_user(db)
    agent = make_agent(db, owner_id=user.id)
    actor = make_actor(db, user.id, actor_id=agent.id)
    repository = make_repository(db, user.id)
    db.commit()

    monkeypatch.setattr(
        ChangePolicyService,
        "evaluate",
        lambda self, change: PolicyDecision(
            decision="review",
            reason="Medium risk requires review",
            reasons=["Medium risk"],
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
        repository=repository,
        actor=actor,
        base_commit="a" * 40,
        resulting_commit="b" * 40,
        intent="Git push medium change",
        risk_level="medium",
        metadata_json='{"ref": "refs/heads/main"}',
    )

    assert change.status == "proposed"


def test_duplicate_git_push_is_idempotent(client: TestClient, db: Session, monkeypatch):
    from app.services.change_service import ChangeService

    user = make_user(db)
    agent = make_agent(db, owner_id=user.id)
    actor = make_actor(db, user.id, actor_id=agent.id)
    repository = make_repository(db, user.id)
    db.commit()

    monkeypatch.setattr(
        ChangePolicyService,
        "evaluate",
        lambda self, change: PolicyDecision(
            decision="review",
            reason="Medium risk requires review",
            reasons=["Medium risk"],
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

    change1 = service.record_agent_push(
        repository=repository,
        actor=actor,
        base_commit="a" * 40,
        resulting_commit="b" * 40,
        intent="Git push medium change",
        risk_level="medium",
        metadata_json='{"ref": "refs/heads/main"}',
    )

    change2 = service.record_agent_push(
        repository=repository,
        actor=actor,
        base_commit="a" * 40,
        resulting_commit="b" * 40,
        intent="Git push medium change",
        risk_level="medium",
        metadata_json='{"ref": "refs/heads/main"}',
    )

    assert change1.id == change2.id
