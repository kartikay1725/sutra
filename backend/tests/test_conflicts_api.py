import json

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
    user_id: str = "owner-1",
    username: str = "sutra-owner",
) -> User:
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
    repository_id: str,
) -> Repository:
    repository = Repository(
        id=repository_id,
        owner_id=owner_id,
        name=f"Repository {repository_id}",
        slug=f"repository-{repository_id}",
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
    actor_id: str,
) -> Actor:
    actor = Actor(
        id=actor_id,
        type="agent",
        name=f"Agent {actor_id}",
        owner_id=owner_id,
        capabilities=json.dumps(
            [
                "repository.read",
                "change.create",
            ]
        ),
    )

    db.add(actor)
    db.flush()

    return actor


def make_change(
    db: Session,
    repository_id: str,
    actor_id: str,
    change_id: str,
    *,
    status: str = "recorded",
    base_commit: str = "123456789abcdef",
    resulting_commit: str | None = "abcdef123456789",
) -> Change:
    change = Change(
        id=change_id,
        repository_id=repository_id,
        actor_id=actor_id,
        intent=f"Change {change_id}",
        base_commit=base_commit,
        resulting_commit=resulting_commit,
        status=status,
        risk_level="low",
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


def test_analyze_conflicts_returns_no_conflict(
    client,
    db,
    monkeypatch,
):
    user = make_user(db)

    repository = make_repository(
        db,
        user.id,
        "repo-1",
    )

    actor = make_actor(
        db,
        user.id,
        "actor-1",
    )

    change = make_change(
        db,
        repository.id,
        actor.id,
        "change-1",
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
            reason="No recorded changes to compare against.",
            paths=[],
            related_change_ids=[],
        ),
    )

    response = client.get(
        f"/v1/changes/{change.id}/conflicts",
        headers=auth_headers(user),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["change_id"] == change.id
    assert body["level"] == "none"
    assert body["paths"] == []
    assert body["related_change_ids"] == []


def test_analyze_conflicts_returns_actual_conflict(
    client,
    db,
    monkeypatch,
):
    user = make_user(db)

    repository = make_repository(
        db,
        user.id,
        "repo-1",
    )

    actor = make_actor(
        db,
        user.id,
        "actor-1",
    )

    change = make_change(
        db,
        repository.id,
        actor.id,
        "change-1",
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
            reason=(
                "Git three-way merge analysis detected "
                "an actual merge conflict."
            ),
            paths=["README.md"],
            related_change_ids=["change-2"],
        ),
    )

    response = client.get(
        f"/v1/changes/{change.id}/conflicts",
        headers=auth_headers(user),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["level"] == "conflict"
    assert body["paths"] == ["README.md"]
    assert body["related_change_ids"] == ["change-2"]


def test_compare_conflicts_returns_overlap(
    client,
    db,
    monkeypatch,
):
    user = make_user(db)

    repository = make_repository(
        db,
        user.id,
        "repo-1",
    )

    actor = make_actor(
        db,
        user.id,
        "actor-1",
    )

    change = make_change(
        db,
        repository.id,
        actor.id,
        "change-1",
    )

    other_change = make_change(
        db,
        repository.id,
        actor.id,
        "change-2",
        base_commit="222222222222222",
        resulting_commit="bbbbbbbbbbbbbbb",
    )

    db.commit()

    from app.services.conflict_service import (
        ConflictResult,
        ConflictService,
    )

    monkeypatch.setattr(
        ConflictService,
        "compare_changes",
        lambda self, source, target: ConflictResult(
            level=ConflictService.LEVEL_OVERLAP,
            reason=(
                "Changes overlap on files, but Git "
                "determines that they can be merged cleanly."
            ),
            paths=["README.md"],
            related_change_ids=[target.id],
        ),
    )

    response = client.get(
        f"/v1/changes/{change.id}/conflicts/"
        f"{other_change.id}",
        headers=auth_headers(user),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["change_id"] == change.id
    assert body["level"] == "overlap"
    assert body["paths"] == ["README.md"]
    assert body["related_change_ids"] == [
        other_change.id
    ]


def test_compare_conflicts_returns_potential_conflict(
    client,
    db,
    monkeypatch,
):
    user = make_user(db)

    repository = make_repository(
        db,
        user.id,
        "repo-1",
    )

    actor = make_actor(
        db,
        user.id,
        "actor-1",
    )

    change = make_change(
        db,
        repository.id,
        actor.id,
        "change-1",
    )

    other_change = make_change(
        db,
        repository.id,
        actor.id,
        "change-2",
        base_commit="222222222222222",
        resulting_commit="bbbbbbbbbbbbbbb",
    )

    db.commit()

    from app.services.conflict_service import (
        ConflictResult,
        ConflictService,
    )

    monkeypatch.setattr(
        ConflictService,
        "compare_changes",
        lambda self, source, target: ConflictResult(
            level=ConflictService.LEVEL_POTENTIAL,
            reason=(
                "Git could not determine a common ancestor "
                "for the two changes."
            ),
            paths=["README.md"],
            related_change_ids=[target.id],
        ),
    )

    response = client.get(
        f"/v1/changes/{change.id}/conflicts/"
        f"{other_change.id}",
        headers=auth_headers(user),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["level"] == "potential_conflict"
    assert body["paths"] == ["README.md"]
    assert body["related_change_ids"] == [
        other_change.id
    ]


def test_compare_conflicts_rejects_different_repositories(
    client,
    db,
):
    user = make_user(db)

    repository_one = make_repository(
        db,
        user.id,
        "repo-1",
    )

    repository_two = make_repository(
        db,
        user.id,
        "repo-2",
    )

    actor = make_actor(
        db,
        user.id,
        "actor-1",
    )

    change_one = make_change(
        db,
        repository_one.id,
        actor.id,
        "change-1",
    )

    change_two = make_change(
        db,
        repository_two.id,
        actor.id,
        "change-2",
        base_commit="222222222222222",
        resulting_commit="bbbbbbbbbbbbbbb",
    )

    db.commit()

    response = client.get(
        f"/v1/changes/{change_one.id}/conflicts/"
        f"{change_two.id}",
        headers=auth_headers(user),
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Changes must belong to the same repository"
    )


def test_compare_conflicts_rejects_other_users_change(
    client,
    db,
):
    owner = make_user(db)

    other_user = make_user(
        db,
        user_id="owner-2",
        username="other-user",
    )

    repository = make_repository(
        db,
        owner.id,
        "repo-1",
    )

    other_repository = make_repository(
        db,
        other_user.id,
        "repo-2",
    )

    owner_actor = make_actor(
        db,
        owner.id,
        "actor-1",
    )

    other_actor = make_actor(
        db,
        other_user.id,
        "actor-2",
    )

    owner_change = make_change(
        db,
        repository.id,
        owner_actor.id,
        "change-1",
    )

    other_change = make_change(
        db,
        other_repository.id,
        other_actor.id,
        "change-2",
    )

    db.commit()

    response = client.get(
        f"/v1/changes/{owner_change.id}/conflicts/"
        f"{other_change.id}",
        headers=auth_headers(owner),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Change not found"


def test_conflicts_endpoint_requires_authentication(
    client,
    db,
):
    user = make_user(db)

    repository = make_repository(
        db,
        user.id,
        "repo-1",
    )

    actor = make_actor(
        db,
        user.id,
        "actor-1",
    )

    change = make_change(
        db,
        repository.id,
        actor.id,
        "change-1",
    )

    db.commit()

    response = client.get(
        f"/v1/changes/{change.id}/conflicts"
    )

    assert response.status_code == 401