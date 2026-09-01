import uuid

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
from app.models.change_review import ChangeReview
from app.models.repository import Repository
from app.models.user import User


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
    from tests.conftest import ensure_test_actor
    ensure_test_actor(db, user)
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
) -> Actor:
    actor = Actor(
        id=str(uuid.uuid4()),
        type="agent",
        name=f"agent-{uuid.uuid4().hex[:8]}",
        owner_id=owner_id,
        capabilities='["repository.read", "change.create"]',
    )

    db.add(actor)
    db.flush()

    return actor


def make_change(
    db: Session,
    repository_id: str,
    actor_id: str,
    risk_level: str = "low",
) -> Change:
    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repository_id,
        actor_id=actor_id,
        intent="Test change",
        base_commit="a" * 40,
        resulting_commit="b" * 40,
        status="proposed",
        risk_level=risk_level,
        metadata_json="{}",
    )

    db.add(change)
    db.flush()

    return change


def auth_headers(user: User):
    token = create_access_token(
        user.id,
    )

    return {
        "Authorization": f"Bearer {token}",
    }


def test_create_review(
    client: TestClient,
    db: Session,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.post(
        f"/v1/changes/{change.id}/reviews",
        json={
            "reason": "Please review this change",
        },
        headers=auth_headers(user),
    )

    assert response.status_code == 201

    body = response.json()

    assert body["change_id"] == change.id
    assert body["requested_by"] == user.id
    assert body["status"] == "pending"
    assert body["reason"] == "Please review this change"
    assert body["reviewer_id"] is None


def test_create_review_without_reason(
    client: TestClient,
    db: Session,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.post(
        f"/v1/changes/{change.id}/reviews",
        json={},
        headers=auth_headers(user),
    )

    assert response.status_code == 201
    assert response.json()["reason"] is None


def test_blocked_change_cannot_enter_review(
    client: TestClient,
    db: Session,
    monkeypatch,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    from app.services.change_policy_service import (
        PolicyDecision,
        ChangePolicyService,
    )

    monkeypatch.setattr(
        ChangePolicyService,
        "evaluate",
        lambda self, change: PolicyDecision(
            decision="block",
            reason="Critical change",
            reasons=["Critical change"],
            conflict_level="none",
            related_change_ids=[],
            dependency_count=0,
            capabilities=[],
        ),
    )

    response = client.post(
        f"/v1/changes/{change.id}/reviews",
        json={},
        headers=auth_headers(user),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Blocked changes cannot enter review"
    )


def test_duplicate_pending_review_is_rejected(
    client: TestClient,
    db: Session,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    first = client.post(
        f"/v1/changes/{change.id}/reviews",
        json={},
        headers=auth_headers(user),
    )

    assert first.status_code == 201

    second = client.post(
        f"/v1/changes/{change.id}/reviews",
        json={},
        headers=auth_headers(user),
    )

    assert second.status_code == 409


def test_list_reviews(
    client: TestClient,
    db: Session,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    create_response = client.post(
        f"/v1/changes/{change.id}/reviews",
        json={"reason": "Review me"},
        headers=auth_headers(user),
    )

    assert create_response.status_code == 201

    response = client.get(
        f"/v1/changes/{change.id}/reviews",
        headers=auth_headers(user),
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["change_id"] == change.id


def test_reviewer_can_approve_review(
    client: TestClient,
    db: Session,
):
    owner = make_user(
        db,
        user_id="owner",
        username="owner",
    )

    reviewer = make_user(
        db,
        user_id="reviewer",
        username="reviewer",
    )

    repository = make_repository(
        db,
        owner.id,
    )

    actor = make_actor(
        db,
        owner.id,
    )

    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    create_response = client.post(
        f"/v1/changes/{change.id}/reviews",
        json={
            "reason": "Needs approval",
        },
        headers=auth_headers(owner),
    )

    assert create_response.status_code == 201

    review_id = create_response.json()["id"]

    response = client.post(
        f"/v1/changes/{change.id}/reviews/{review_id}/approve",
        json={
            "reason": "Approved after review",
        },
        headers=auth_headers(reviewer),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "approved"
    assert body["reviewer_id"] == reviewer.id
    assert body["reason"] == "Approved after review"
    assert body["reviewed_at"] is not None


def test_reviewer_can_reject_review(
    client: TestClient,
    db: Session,
):
    owner = make_user(
        db,
        user_id="owner-reject",
        username="owner-reject",
    )

    reviewer = make_user(
        db,
        user_id="reviewer-reject",
        username="reviewer-reject",
    )

    repository = make_repository(
        db,
        owner.id,
    )

    actor = make_actor(
        db,
        owner.id,
    )

    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    create_response = client.post(
        f"/v1/changes/{change.id}/reviews",
        json={},
        headers=auth_headers(owner),
    )

    review_id = create_response.json()["id"]

    response = client.post(
        f"/v1/changes/{change.id}/reviews/{review_id}/reject",
        json={
            "reason": "Rejected because more work is required",
        },
        headers=auth_headers(reviewer),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "rejected"
    assert body["reviewer_id"] == reviewer.id
    assert body["reviewed_at"] is not None


def test_requester_cannot_approve_own_review(
    client: TestClient,
    db: Session,
):
    owner = make_user(db)
    repository = make_repository(db, owner.id)
    actor = make_actor(db, owner.id)
    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    create_response = client.post(
        f"/v1/changes/{change.id}/reviews",
        json={},
        headers=auth_headers(owner),
    )

    review_id = create_response.json()["id"]

    response = client.post(
        f"/v1/changes/{change.id}/reviews/{review_id}/approve",
        json={},
        headers=auth_headers(owner),
    )

    assert response.status_code == 403


def test_requester_cannot_reject_own_review(
    client: TestClient,
    db: Session,
):
    owner = make_user(db)
    repository = make_repository(db, owner.id)
    actor = make_actor(db, owner.id)
    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    create_response = client.post(
        f"/v1/changes/{change.id}/reviews",
        json={},
        headers=auth_headers(owner),
    )

    review_id = create_response.json()["id"]

    response = client.post(
        f"/v1/changes/{change.id}/reviews/{review_id}/reject",
        json={},
        headers=auth_headers(owner),
    )

    assert response.status_code == 403


def test_approved_review_cannot_be_approved_again(
    client: TestClient,
    db: Session,
):
    owner = make_user(
        db,
        user_id="approval-owner",
        username="approval-owner",
    )

    reviewer = make_user(
        db,
        user_id="approval-reviewer",
        username="approval-reviewer",
    )

    repository = make_repository(db, owner.id)
    actor = make_actor(db, owner.id)
    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    create_response = client.post(
        f"/v1/changes/{change.id}/reviews",
        json={},
        headers=auth_headers(owner),
    )

    review_id = create_response.json()["id"]

    first = client.post(
        f"/v1/changes/{change.id}/reviews/{review_id}/approve",
        json={},
        headers=auth_headers(reviewer),
    )

    assert first.status_code == 200

    second = client.post(
        f"/v1/changes/{change.id}/reviews/{review_id}/approve",
        json={},
        headers=auth_headers(reviewer),
    )

    assert second.status_code == 409


def test_rejected_review_cannot_be_approved(
    client: TestClient,
    db: Session,
):
    owner = make_user(
        db,
        user_id="rejected-owner",
        username="rejected-owner",
    )

    reviewer = make_user(
        db,
        user_id="rejected-reviewer",
        username="rejected-reviewer",
    )

    repository = make_repository(db, owner.id)
    actor = make_actor(db, owner.id)
    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    create_response = client.post(
        f"/v1/changes/{change.id}/reviews",
        json={},
        headers=auth_headers(owner),
    )

    review_id = create_response.json()["id"]

    first = client.post(
        f"/v1/changes/{change.id}/reviews/{review_id}/reject",
        json={},
        headers=auth_headers(reviewer),
    )

    assert first.status_code == 200

    second = client.post(
        f"/v1/changes/{change.id}/reviews/{review_id}/approve",
        json={},
        headers=auth_headers(reviewer),
    )

    assert second.status_code == 409


def test_other_user_cannot_access_review(
    client: TestClient,
    db: Session,
):
    owner = make_user(
        db,
        user_id="review-owner",
        username="review-owner",
    )

    other = make_user(
        db,
        user_id="review-other",
        username="review-other",
    )

    repository = make_repository(
        db,
        owner.id,
    )

    actor = make_actor(
        db,
        owner.id,
    )

    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.post(
        f"/v1/changes/{change.id}/reviews",
        json={},
        headers=auth_headers(other),
    )

    assert response.status_code == 404


def test_unknown_change_is_rejected(
    client: TestClient,
    db: Session,
):
    user = make_user(db)
    db.commit()

    response = client.get(
        "/v1/changes/does-not-exist/reviews",
        headers=auth_headers(user),
    )

    assert response.status_code == 404


def test_review_requires_authentication(
    client: TestClient,
    db: Session,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.get(
        f"/v1/changes/{change.id}/reviews",
    )

    assert response.status_code == 401


def test_review_is_persisted(
    client: TestClient,
    db: Session,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.post(
        f"/v1/changes/{change.id}/reviews",
        json={
            "reason": "Persistence test",
        },
        headers=auth_headers(user),
    )

    assert response.status_code == 201

    review_id = response.json()["id"]

    review = db.scalar(
        select(ChangeReview).where(
            ChangeReview.id == review_id
        )
    )

    assert review is not None
    assert review.change_id == change.id
    assert review.requested_by == user.id
    assert review.status == "pending"