import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models.actor import Actor
from app.models.change import Change
from app.models.repository import Repository
from app.models.user import User
from app.core.security import create_access_token


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
    user = User(
        id="owner-1",
        username="sutra-owner",
        email="sutra-owner@example.com",
        password_hash="test-password-hash",
    )

    db.add(user)
    db.flush()

    from tests.conftest import ensure_test_actor
    ensure_test_actor(db, user)

    return user


def make_repository(db: Session, owner_id: str) -> Repository:
    repository = Repository(
        id="repo-1",
        owner_id=owner_id,
        name="Test Repository",
        slug="test-repository",
        visibility="private",
        default_branch="main",
        storage_key="test-repository.git",
    )

    db.add(repository)
    db.flush()

    return repository


def make_actor(
    db: Session,
    owner_id: str,
    capabilities=None,
) -> Actor:
    if capabilities is None:
        capabilities = [
            "repository.read",
            "change.create",
        ]

    actor = Actor(
        id="actor-1",
        type="agent",
        name="Test Agent",
        owner_id=owner_id,
        capabilities=json.dumps(capabilities),
    )

    db.add(actor)
    db.flush()

    return actor


def make_change(
    db: Session,
    repository_id: str,
    actor_id: str,
    *,
    risk_level="low",
    status="recorded",
    resulting_commit="abcdef123456789",
) -> Change:
    change = Change(
        id="change-1",
        repository_id=repository_id,
        actor_id=actor_id,
        intent="Test change",
        base_commit="123456789abcdef",
        resulting_commit=resulting_commit,
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


def test_policy_endpoint_allows_clean_low_risk_change(
    client,
    db,
    monkeypatch,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = make_change(
        db,
        repository.id,
        actor.id,
        risk_level="low",
    )

    db.commit()

    from app.services.conflict_service import (
        ConflictResult,
        ConflictService,
    )

    monkeypatch.setattr(
        ConflictService,
        "analyze",
        lambda self, change: ConflictResult(
            level=ConflictService.LEVEL_NONE,
            reason="No conflict",
            paths=[],
            related_change_ids=[],
        ),
    )

    response = client.get(
        f"/v1/changes/{change.id}/policy",
        headers=auth_headers(user),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["change_id"] == change.id
    assert body["decision"] == "allow"
    assert body["conflict_level"] == "none"
    assert body["related_change_ids"] == []
    assert "repository.read" in body["capabilities"]
    assert "change.create" in body["capabilities"]


def test_policy_endpoint_blocks_actual_conflict(
    client,
    db,
    monkeypatch,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = make_change(
        db,
        repository.id,
        actor.id,
        risk_level="low",
    )

    db.commit()

    from app.services.conflict_service import (
        ConflictResult,
        ConflictService,
    )

    monkeypatch.setattr(
        ConflictService,
        "analyze",
        lambda self, change: ConflictResult(
            level=ConflictService.LEVEL_CONFLICT,
            reason="Git detected an actual merge conflict.",
            paths=["README.md"],
            related_change_ids=["other-change"],
        ),
    )

    response = client.get(
        f"/v1/changes/{change.id}/policy",
        headers=auth_headers(user),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["change_id"] == change.id
    assert body["decision"] == "block"
    assert body["conflict_level"] == "conflict"
    assert body["related_change_ids"] == ["other-change"]

    assert (
        body["reason"]
        == "Change is blocked because Git detected "
        "an actual merge conflict."
    )


def test_policy_endpoint_requires_review_for_high_risk_change(
    client,
    db,
    monkeypatch,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)
    change = make_change(
        db,
        repository.id,
        actor.id,
        risk_level="high",
    )

    db.commit()

    from app.services.conflict_service import (
        ConflictResult,
        ConflictService,
    )

    monkeypatch.setattr(
        ConflictService,
        "analyze",
        lambda self, change: ConflictResult(
            level=ConflictService.LEVEL_NONE,
            reason="No conflict",
            paths=[],
            related_change_ids=[],
        ),
    )

    response = client.get(
        f"/v1/changes/{change.id}/policy",
        headers=auth_headers(user),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["decision"] == "review"
    assert body["conflict_level"] == "none"

    assert any(
        "High-risk" in reason
        for reason in body["reasons"]
    )


def test_policy_endpoint_blocks_missing_capability(
    client,
    db,
    monkeypatch,
):
    user = make_user(db)
    repository = make_repository(db, user.id)

    actor = make_actor(
        db,
        user.id,
        capabilities=["repository.read"],
    )

    change = make_change(
        db,
        repository.id,
        actor.id,
        risk_level="low",
    )

    db.commit()

    from app.services.conflict_service import (
        ConflictResult,
        ConflictService,
    )

    monkeypatch.setattr(
        ConflictService,
        "analyze",
        lambda self, change: ConflictResult(
            level=ConflictService.LEVEL_NONE,
            reason="No conflict",
            paths=[],
            related_change_ids=[],
        ),
    )

    response = client.get(
        f"/v1/changes/{change.id}/policy",
        headers=auth_headers(user),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["decision"] == "block"
    assert "change.create" not in body["capabilities"]

    assert any(
        "change.create" in reason
        for reason in body["reasons"]
    )


def test_policy_endpoint_rejects_change_owned_by_another_user(
    client,
    db,
    monkeypatch,
):
    owner = make_user(db)

    other_user = User(
        id="owner-2",
        username="other-user",
        email="other@example.com",
        password_hash="test-password-hash",
    )

    db.add(other_user)
    db.flush()

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

    response = client.get(
        f"/v1/changes/{change.id}/policy",
        headers=auth_headers(other_user),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Change not found"


def test_policy_endpoint_requires_authentication(
    client,
    db,
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
        f"/v1/changes/{change.id}/policy"
    )

    assert response.status_code == 401