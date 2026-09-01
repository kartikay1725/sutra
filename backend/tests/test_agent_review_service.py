from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.inline_review_comment import InlineReviewComment
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.agent_review_service import AgentReviewService
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService


def setup_agent_service_fixtures(db):
    user_a = User(
        id=str(uuid4()),
        username=f"ag_svc_a_{uuid4().hex[:8]}",
        email=f"agsvca_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    user_b = User(
        id=str(uuid4()),
        username=f"ag_svc_b_{uuid4().hex[:8]}",
        email=f"agsvcb_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    db.add_all([user_a, user_b])
    db.flush()

    # PullRequestService resolves human authors through the Actor table.
    # Create the corresponding human actors explicitly so this fixture does
    # not depend on global Session event hooks.
    human_actor_a = Actor(
        id=user_a.id,
        owner_id=user_a.id,
        type="human",
        name=user_a.username,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create"]'
        ),
    )

    human_actor_b = Actor(
        id=user_b.id,
        owner_id=user_b.id,
        type="human",
        name=user_b.username,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create"]'
        ),
    )

    db.add_all([
        human_actor_a,
        human_actor_b,
    ])
    db.flush()

    repo_a = RepositoryService(db).create(
        owner_id=user_a.id,
        name=f"ag_svc_repo_a_{uuid4().hex[:8]}",
        description="Agent Service Repo A",
        visibility="private",
    )

    repo_b = RepositoryService(db).create(
        owner_id=user_b.id,
        name=f"ag_svc_repo_b_{uuid4().hex[:8]}",
        description="Agent Service Repo B",
        visibility="private",
    )

    agent_a = Agent(
        id=str(uuid4()),
        owner_id=user_a.id,
        name="agent_a",
        token_prefix="prefix_aga_123",
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

    agent_b = Agent(
        id=str(uuid4()),
        owner_id=user_b.id,
        name="agent_b",
        token_prefix="prefix_agb_456",
        token_hash="hash",
        is_active=True,
        status="active",
    )

    db.add(agent_b)

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

    db.add(actor_b)
    db.commit()

    change_a = Change(
        id=str(uuid4()),
        repository_id=repo_a.id,
        actor_id=actor_a.id,
        intent="Agent Change A",
        risk_level="low",
        resulting_commit="1111111111111111111111111111111111111111",
        base_commit="0000000000000000000000000000000000000000",
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
        "Agent PR A",
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
        change_a,
        pr_a,
    )


def test_agent_authorization_boundaries(db):
    (
        user_a,
        user_b,
        repo_a,
        repo_b,
        agent_a,
        agent_b,
        change_a,
        pr_a,
    ) = setup_agent_service_fixtures(db)

    svc = AgentReviewService(db)

    # Agent A (owned by User A) commenting on PR A
    # (Repo A owned by User A) -> Success
    comment = svc.create_agent_comment(
        agent_id=agent_a.id,
        pull_request_id=pr_a.id,
        body="Agent A authorized comment",
    )

    assert comment is not None
    assert comment.pull_request_id == pr_a.id

    # Agent B (owned by User B) attempting to comment on PR A
    # (Repo A owned by User A) -> PermissionError
    with pytest.raises(
        PermissionError,
        match="Actor does not own the target repository",
    ):
        svc.create_agent_comment(
            agent_id=agent_b.id,
            pull_request_id=pr_a.id,
            body="Agent B unauthorized comment",
        )


def test_agent_review_findings_validation(db):
    (
        user_a,
        user_b,
        repo_a,
        repo_b,
        agent_a,
        agent_b,
        change_a,
        pr_a,
    ) = setup_agent_service_fixtures(db)

    svc = AgentReviewService(db)

    finding = svc.create_agent_finding(
        agent_id=agent_a.id,
        pull_request_id=pr_a.id,
        severity="high",
        category="security",
        message="SQL injection risk detected",
        path="src/db.py",
        line_number=45,
        suggested_fix="Use parameterized query",
    )

    assert finding is not None
    assert "[HIGH] [SECURITY]" in finding.body

    with pytest.raises(
        ValueError,
        match="Invalid severity",
    ):
        svc.create_agent_finding(
            agent_id=agent_a.id,
            pull_request_id=pr_a.id,
            severity="extreme",
            category="security",
            message="Invalid severity test",
        )

    with pytest.raises(
        ValueError,
        match="Invalid category",
    ):
        svc.create_agent_finding(
            agent_id=agent_a.id,
            pull_request_id=pr_a.id,
            severity="high",
            category="magic",
            message="Invalid category test",
        )


def test_agent_review_summary_service(db):
    (
        user_a,
        user_b,
        repo_a,
        repo_b,
        agent_a,
        agent_b,
        change_a,
        pr_a,
    ) = setup_agent_service_fixtures(db)

    svc = AgentReviewService(db)

    svc.create_agent_finding(
        agent_id=agent_a.id,
        pull_request_id=pr_a.id,
        severity="critical",
        category="security",
        message="Hardcoded secret found",
    )

    svc.create_agent_finding(
        agent_id=agent_a.id,
        pull_request_id=pr_a.id,
        severity="low",
        category="style",
        message="Unused variable",
    )

    summary = svc.get_agent_review_summary(
        pr_a.id,
        user_a.id,
        is_agent=False,
    )

    assert summary["total_findings"] == 2
    assert summary["severity_distribution"]["critical"] == 1
    assert summary["severity_distribution"]["low"] == 1
    assert len(summary["participating_agent_ids"]) == 1


def test_gate_18h_human_agent_review_boundary(db):
    (
        user_a,
        user_b,
        repo_a,
        repo_b,
        agent_a,
        agent_b,
        change_a,
        pr_a,
    ) = setup_agent_service_fixtures(db)

    svc = AgentReviewService(db)

    svc.create_agent_finding(
        agent_id=agent_a.id,
        pull_request_id=pr_a.id,
        severity="low",
        category="style",
        message="Looks clean!",
    )

    reviews = db.scalars(
        select(ChangeReview).where(
            ChangeReview.change_id == change_a.id
        )
    ).all()

    for rev in reviews:
        assert rev.status != "approved"

    pr_current = db.scalar(
        select(PullRequest).where(
            PullRequest.id == pr_a.id
        )
    )

    assert pr_current.status == PullRequest.STATUS_OPEN