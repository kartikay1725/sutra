from uuid import uuid4

import pytest

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.user import User
from app.services.branch_protection_service import (
    BranchProtectionService,
)
from app.services.pull_request_service import (
    PullRequestService,
)
from app.services.repository_service import (
    RepositoryService,
)


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


def setup_sec_bp_fixtures(db):
    user_a = User(
        id=str(uuid4()),
        username=f"sec_bp_user_a_{uuid4().hex[:8]}",
        email=f"secbpa_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    user_b = User(
        id=str(uuid4()),
        username=f"sec_bp_user_b_{uuid4().hex[:8]}",
        email=f"secbpb_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    db.add_all(
        [
            user_a,
            user_b,
        ]
    )
    db.flush()

    # Both users participate in authorization operations, and user_a
    # is also the PullRequest author. Create their Actor identities
    # explicitly rather than relying on a global Session event.
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
        name=f"sec_bp_repo_a_{uuid4().hex[:8]}",
        description="Sec BP Repo A",
        visibility="private",
    )

    repo_b = RepositoryService(db).create(
        owner_id=user_b.id,
        name=f"sec_bp_repo_b_{uuid4().hex[:8]}",
        description="Sec BP Repo B",
        visibility="private",
    )

    agent_a = Agent(
        id=str(uuid4()),
        owner_id=user_a.id,
        name="sec_bp_agent_a",
        token_prefix="prefix_secbpa_1",
        token_hash="hash",
        is_active=True,
        status="active",
    )

    db.add(agent_a)

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

    db.add(actor_a)
    db.commit()

    change_a = Change(
        id=str(uuid4()),
        repository_id=repo_a.id,
        actor_id=actor_a.id,
        intent="Sec BP Change A",
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

    pr_svc = PullRequestService(db)

    pr_a = pr_svc.create_pull_request(
        repo_a.id,
        user_a.id,
        change_a.id,
        "Sec BP PR A",
        "main",
    )

    db.commit()

    return (
        user_a,
        user_b,
        repo_a,
        repo_b,
        change_a,
        pr_a,
    )


def test_branch_protection_cross_repository_and_authorization_isolation(
    db,
):
    (
        user_a,
        user_b,
        repo_a,
        repo_b,
        change_a,
        pr_a,
    ) = setup_sec_bp_fixtures(db)

    svc = BranchProtectionService(db)

    # 1. User A creates rule on Repo A -> Success.
    rule_a = svc.create_rule(
        repository_id=repo_a.id,
        actor_user_id=user_a.id,
        branch_pattern="main",
        required_approvals=1,
    )

    assert rule_a is not None

    # 2. User B attempts to create rule on Repo A -> PermissionError.
    with pytest.raises(
        PermissionError,
        match=(
            "User is not authorized to manage "
            "branch protection rules"
        ),
    ):
        svc.create_rule(
            repository_id=repo_a.id,
            actor_user_id=user_b.id,
            branch_pattern="main",
        )

    # 3. User B attempts to update rule on Repo A -> PermissionError.
    with pytest.raises(
        PermissionError,
        match=(
            "User is not authorized to manage "
            "branch protection rules"
        ),
    ):
        svc.update_rule(
            rule_id=rule_a.id,
            actor_user_id=user_b.id,
            required_approvals=0,
        )

    # 4. User B attempts to delete rule on Repo A -> PermissionError.
    with pytest.raises(
        PermissionError,
        match=(
            "User is not authorized to manage "
            "branch protection rules"
        ),
    ):
        svc.delete_rule(
            rule_id=rule_a.id,
            actor_user_id=user_b.id,
        )


def test_branch_pattern_validation_and_injection_prevention(
    db,
):
    (
        user_a,
        user_b,
        repo_a,
        repo_b,
        change_a,
        pr_a,
    ) = setup_sec_bp_fixtures(db)

    svc = BranchProtectionService(db)

    # Shell injection attempt in branch pattern.
    with pytest.raises(
        ValueError,
        match="Invalid branch pattern",
    ):
        svc.create_rule(
            repository_id=repo_a.id,
            actor_user_id=user_a.id,
            branch_pattern="main; rm -rf /",
        )

    # Directory traversal attempt in branch pattern.
    with pytest.raises(
        ValueError,
        match="Invalid branch pattern",
    ):
        svc.create_rule(
            repository_id=repo_a.id,
            actor_user_id=user_a.id,
            branch_pattern="refs/heads/../../main",
        )