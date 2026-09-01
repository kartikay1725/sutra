from uuid import uuid4

import pytest
from fastapi import status

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.user import User
from app.services.agent_review_service import AgentReviewService
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService


def _create_human_actor(
    db,
    user: User,
) -> Actor:
    actor = Actor(
        id=user.id,
        owner_id=user.id,
        type="human",
        name=user.username,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create", '
            '"change.review", '
            '"change.approve"]'
        ),
    )

    db.add(actor)
    db.flush()

    return actor


def setup_sec_agent_fixtures(db):
    user_a = User(
        id=str(uuid4()),
        username=f"sec_ag_user_a_{uuid4().hex[:8]}",
        email=f"secaga_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    user_b = User(
        id=str(uuid4()),
        username=f"sec_ag_user_b_{uuid4().hex[:8]}",
        email=f"secagb_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    db.add_all(
        [
            user_a,
            user_b,
        ]
    )
    db.flush()

    _create_human_actor(
        db,
        user_a,
    )

    _create_human_actor(
        db,
        user_b,
    )

    repo_a = RepositoryService(db).create(
        owner_id=user_a.id,
        name=f"sec_ag_repo_a_{uuid4().hex[:8]}",
        description="Sec Agent Repo A",
        visibility="private",
    )

    repo_b = RepositoryService(db).create(
        owner_id=user_b.id,
        name=f"sec_ag_repo_b_{uuid4().hex[:8]}",
        description="Sec Agent Repo B",
        visibility="private",
    )

    agent_a = Agent(
        id=str(uuid4()),
        owner_id=user_a.id,
        name="sec_agent_a",
        token_prefix="prefix_secag_12",
        token_hash="hash",
        is_active=True,
        status="active",
    )

    agent_b = Agent(
        id=str(uuid4()),
        owner_id=user_b.id,
        name="sec_agent_b",
        token_prefix="prefix_secag_34",
        token_hash="hash",
        is_active=True,
        status="active",
    )

    agent_inactive = Agent(
        id=str(uuid4()),
        owner_id=user_a.id,
        name="sec_agent_inact",
        token_prefix="prefix_secag_56",
        token_hash="hash",
        is_active=False,
        status="revoked",
    )

    db.add_all(
        [
            agent_a,
            agent_b,
            agent_inactive,
        ]
    )

    actor_a = Actor(
        id=agent_a.id,
        owner_id=user_a.id,
        type="agent",
        name=agent_a.name,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create"]'
        ),
    )

    actor_b = Actor(
        id=agent_b.id,
        owner_id=user_b.id,
        type="agent",
        name=agent_b.name,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create"]'
        ),
    )

    actor_inactive = Actor(
        id=agent_inactive.id,
        owner_id=user_a.id,
        type="agent",
        name=agent_inactive.name,
        capabilities=(
            '["repository.read", '
            '"repository.write"]'
        ),
    )

    db.add_all(
        [
            actor_a,
            actor_b,
            actor_inactive,
        ]
    )

    db.commit()

    from app.models.agent_repository_access import AgentRepositoryAccess
    import json
    db.add_all([
        AgentRepositoryAccess(
            agent_id=agent_a.id,
            repository_id=repo_a.id,
            permissions=json.dumps(["repository.read", "repository.write", "change.create"]),
            enabled=True,
        ),
        AgentRepositoryAccess(
            agent_id=agent_b.id,
            repository_id=repo_b.id,
            permissions=json.dumps(["repository.read", "repository.write", "change.create"]),
            enabled=True,
        ),
    ])
    db.commit()

    change_a = Change(
        id=str(uuid4()),
        repository_id=repo_a.id,
        actor_id=actor_a.id,
        intent="Sec Agent Change A",
        risk_level="low",
        resulting_commit=(
            "1111111111111111111111111111111111111111"
        ),
        base_commit=(
            "0000000000000000000000000000000000000000"
        ),
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )

    db.add(change_a)
    db.commit()

    svc = PullRequestService(db)

    pr_a = svc.create_pull_request(
        repo_a.id,
        user_a.id,
        change_a.id,
        "Sec Agent PR A",
        "main",
    )

    db.commit()

    return (
        user_a,
        user_b,
        repo_a,
        repo_b,
        agent_a,
        agent_b,
        agent_inactive,
        change_a,
        pr_a,
    )


def test_agent_capability_and_repo_ownership_bypass_prevention(db):
    (
        user_a,
        user_b,
        repo_a,
        repo_b,
        agent_a,
        agent_b,
        agent_inactive,
        change_a,
        pr_a,
    ) = setup_sec_agent_fixtures(db)

    svc = AgentReviewService(db)

    # Inactive agent must be rejected.
    with pytest.raises(
        PermissionError,
        match="Agent is inactive or not found",
    ):
        svc.create_agent_comment(
            agent_id=agent_inactive.id,
            pull_request_id=pr_a.id,
            body="Inactive agent attempt",
        )

    # Agent B must not operate on User A's repository.
    with pytest.raises(
        PermissionError,
        match="Actor does not own the target repository",
    ):
        svc.create_agent_comment(
            agent_id=agent_b.id,
            pull_request_id=pr_a.id,
            body="Cross-owner agent attempt",
        )


def test_agent_review_security_api_isolation(
    db,
    client,
):
    (
        user_a,
        user_b,
        repo_a,
        repo_b,
        agent_a,
        agent_b,
        agent_inactive,
        change_a,
        pr_a,
    ) = setup_sec_agent_fixtures(db)

    from app.api.agent_dependencies import get_current_agent
    from app.main import app

    app.dependency_overrides[
        get_current_agent
    ] = lambda: agent_b

    payload = {
        "severity": "high",
        "category": "security",
        "message": "Attack attempt",
    }

    res = client.post(
        f"/v1/pull-requests/{pr_a.id}/agent-reviews/findings",
        json=payload,
    )

    assert res.status_code in {
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    }

    app.dependency_overrides.clear()