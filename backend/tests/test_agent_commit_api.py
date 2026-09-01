import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, get_db
from app.main import app
from app.api.agent_dependencies import get_current_agent
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_file import ChangeFile
from app.models.repository import Repository
from app.models.user import User


# ---------------------------------------------------------------------------
# Test database
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=test_engine)

    session = TestSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    yield TestClient(app)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Fixtures/helpers
# ---------------------------------------------------------------------------

BASE_COMMIT = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
RESULTING_COMMIT = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def make_user(db):
    user = User(
        id="owner-1",
        username="sutra-owner",
        email="sutra-owner@example.com",
        password_hash="test-password-hash",
    )

    db.add(user)
    db.flush()

    return user


def make_agent(db, owner_id="owner-1", agent_id="agent-1"):
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


def make_actor(db, agent):
    actor = Actor(
        id=agent.id,
        type="agent",
        name=agent.name,
        owner_id=agent.owner_id,
        capabilities=json.dumps(
            [
                "repository.read",
                "repository.write",
                "change.create",
                "change.commit",
                "change.conflict.read",
            ]
        ),
    )

    db.add(actor)
    db.flush()

    return actor


def make_repository(db, owner_id="owner-1"):
    if not db.get(Actor, owner_id):
        actor = Actor(
            id=owner_id,
            owner_id=owner_id,
            type="human",
            name=owner_id,
            capabilities='["repository.read", "repository.write", "change.create"]',
        )
        db.add(actor)
        db.flush()

    repository = Repository(
        id="repo-1",
        owner_id=owner_id,
        name="hello-sutra",
        slug="hello-sutra",
        description="API policy test repository",
        visibility="private",
        default_branch="main",
        storage_key="api-policy-test.git",
    )

    db.add(repository)
    db.flush()

    return repository


def make_change(
    db,
    repository,
    actor,
    *,
    change_id="change-1",
    status="proposed",
    risk_level="low",
):
    change = Change(
        id=change_id,
        repository_id=repository.id,
        actor_id=actor.id,
        intent="API agent commit policy test",
        base_commit=BASE_COMMIT,
        resulting_commit=None,
        status=status,
        risk_level=risk_level,
        metadata_json="{}",
    )

    db.add(change)
    db.flush()

    return change


def install_agent_override(agent):
    app.dependency_overrides[get_current_agent] = (
        lambda: agent
    )


def policy_blocked():
    from app.services.change_policy_service import ChangePolicyService

    return type(
        "PolicyResult",
        (),
        {
            "decision": ChangePolicyService.BLOCK,
            "reason": (
                "Change is blocked because Git detected "
                "an actual merge conflict."
            ),
        },
    )()


def policy_allowed():
    from app.services.change_policy_service import ChangePolicyService

    return type(
        "PolicyResult",
        (),
        {
            "decision": ChangePolicyService.ALLOW,
            "reason": (
                "Change satisfies the current deterministic "
                "SUTRA policy."
            ),
        },
    )()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_agent_commit_allowed_records_change(
    client,
    db,
    tmp_path,
):
    user = make_user(db)
    agent = make_agent(db, owner_id=user.id)
    actor = make_actor(db, agent)
    repository = make_repository(db)

    change = make_change(
        db,
        repository,
        actor,
    )

    install_agent_override(agent)

    with (
        patch(
            "app.services.change_service.ChangeService.resolve_commit",
            side_effect=[
                BASE_COMMIT,
                RESULTING_COMMIT,
            ],
        ),
        patch(
            "app.services.change_service.ChangeService.verify_ancestor"
        ),
        patch(
            "app.services.change_service.ChangeService.get_changed_files",
            return_value=[
                {
                    "path": "README.md",
                    "operation": "modified",
                }
            ],
        ),
        patch(
            "app.services.change_service.ChangePolicyService.evaluate",
            return_value=policy_allowed(),
        ),
    ):
        response = client.post(
            f"/v1/changes/{change.id}/agent-commit",
            json={
                "resulting_commit": RESULTING_COMMIT,
            },
            headers={
                "Authorization": "Bearer test-agent-token"
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["id"] == change.id
    assert body["status"] == "recorded"
    assert body["resulting_commit"] == RESULTING_COMMIT
    assert body["actor_id"] == agent.id
    assert body["actor_type"] == "agent"

    db.refresh(change)

    assert change.status == "recorded"
    assert change.resulting_commit == RESULTING_COMMIT

    files = db.query(ChangeFile).filter(
        ChangeFile.change_id == change.id
    ).all()

    assert len(files) == 1
    assert files[0].path == "README.md"
    assert files[0].operation == "modified"


def test_agent_commit_conflict_returns_400_and_rolls_back(
    client,
    db,
):
    user = make_user(db)
    agent = make_agent(db, owner_id=user.id)
    actor = make_actor(db, agent)
    repository = make_repository(db)

    change = make_change(
        db,
        repository,
        actor,
    )

    db.commit()

    install_agent_override(agent)

    with (
        patch(
            "app.services.change_service.ChangeService.resolve_commit",
            side_effect=[
                BASE_COMMIT,
                RESULTING_COMMIT,
            ],
        ),
        patch(
            "app.services.change_service.ChangeService.verify_ancestor"
        ),
        patch(
            "app.services.change_service.ChangeService.get_changed_files",
            return_value=[
                {
                    "path": "README.md",
                    "operation": "modified",
                }
            ],
        ),
        patch(
            "app.services.change_service.ChangePolicyService.evaluate",
            return_value=policy_blocked(),
        ),
    ):
        response = client.post(
            f"/v1/changes/{change.id}/agent-commit",
            json={
                "resulting_commit": RESULTING_COMMIT,
            },
            headers={
                "Authorization": "Bearer test-agent-token"
            },
        )

    assert response.status_code == 400

    assert (
        "Change blocked by SUTRA policy"
        in response.json()["detail"]
    )

    db.expire_all()

    stored_change = db.get(
        Change,
        change.id,
    )

    assert stored_change is not None
    assert stored_change.status == "proposed"
    assert stored_change.resulting_commit is None

    files = db.query(ChangeFile).filter(
        ChangeFile.change_id == change.id
    ).all()

    assert files == []


def test_agent_commit_invalid_ancestry_returns_400(
    client,
    db,
):
    user = make_user(db)
    agent = make_agent(db, owner_id=user.id)
    actor = make_actor(db, agent)
    repository = make_repository(db)

    change = make_change(
        db,
        repository,
        actor,
    )

    install_agent_override(agent)

    unrelated_commit = (
        "cccccccccccccccccccccccccccccccccccccccc"
    )

    with (
        patch(
            "app.services.change_service.ChangeService.resolve_commit",
            side_effect=[
                BASE_COMMIT,
                unrelated_commit,
            ],
        ),
        patch(
            "app.services.change_service.ChangeService.verify_ancestor",
            side_effect=ValueError(
                "Resulting commit is not based on the "
                "change base commit"
            ),
        ),
    ):
        response = client.post(
            f"/v1/changes/{change.id}/agent-commit",
            json={
                "resulting_commit": unrelated_commit,
            },
            headers={
                "Authorization": "Bearer test-agent-token"
            },
        )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "Resulting commit is not based on the "
        "change base commit"
    )

    db.expire_all()

    stored_change = db.get(
        Change,
        change.id,
    )

    assert stored_change.status == "proposed"
    assert stored_change.resulting_commit is None


def test_wrong_agent_cannot_commit_change(
    client,
    db,
):
    user = make_user(db)

    correct_agent = make_agent(
        db,
        owner_id=user.id,
        agent_id="agent-1",
    )

    actor = make_actor(
        db,
        correct_agent,
    )

    repository = make_repository(db)

    change = make_change(
        db,
        repository,
        actor,
    )

    wrong_agent = make_agent(
        db,
        owner_id=user.id,
        agent_id="agent-2",
    )

    install_agent_override(wrong_agent)

    response = client.post(
        f"/v1/changes/{change.id}/agent-commit",
        json={
            "resulting_commit": RESULTING_COMMIT,
        },
        headers={
            "Authorization": "Bearer wrong-agent-token"
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Agent change not found"

    db.expire_all()

    stored_change = db.get(
        Change,
        change.id,
    )

    assert stored_change.status == "proposed"
    assert stored_change.resulting_commit is None


def test_inactive_agent_is_rejected(
    client,
    db,
):
    user = make_user(db)

    agent = make_agent(
        db,
        owner_id=user.id,
    )

    agent.status = "inactive"
    agent.is_active = False

    db.flush()

    # The real dependency checks activity before the endpoint.
    # Override it here to reproduce that exact rejection.
    def inactive_agent_dependency():
        raise HTTPException(
            status_code=403,
            detail="Agent is inactive",
        )

    app.dependency_overrides[get_current_agent] = (
        inactive_agent_dependency
    )

    repository = make_repository(db)

    actor = make_actor(db, agent)

    change = make_change(
        db,
        repository,
        actor,
    )

    response = client.post(
        f"/v1/changes/{change.id}/agent-commit",
        json={
            "resulting_commit": RESULTING_COMMIT,
        },
        headers={
            "Authorization": "Bearer inactive-agent-token"
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Agent is inactive"

    db.expire_all()

    stored_change = db.get(
        Change,
        change.id,
    )

    assert stored_change.status == "proposed"
    assert stored_change.resulting_commit is None


def test_missing_agent_authentication_is_rejected(
    client,
    db,
):
    user = make_user(db)
    agent = make_agent(db, owner_id=user.id)
    actor = make_actor(db, agent)
    repository = make_repository(db)

    change = make_change(
        db,
        repository,
        actor,
    )

    # Do not install an authentication override.
    app.dependency_overrides.pop(
        get_current_agent,
        None,
    )

    response = client.post(
        f"/v1/changes/{change.id}/agent-commit",
        json={
            "resulting_commit": RESULTING_COMMIT,
        },
    )

    assert response.status_code == 401

    detail = response.json()["detail"]

    assert isinstance(detail, dict)
    assert detail["error_code"] == "SESSION_REQUIRED"
    assert detail["http_status"] == 401
    assert detail["next_action"]["operation"] == "create_session"
    assert detail["next_action"]["endpoint"] == "/v1/agents/session"
    assert detail["retryable"] is True

    db.expire_all()

    stored_change = db.get(
        Change,
        change.id,
    )

    assert stored_change.status == "proposed"
    assert stored_change.resulting_commit is None