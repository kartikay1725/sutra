from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.inline_review_comment import InlineReviewComment
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.agent_review_service import AgentReviewService
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService


def setup_agent_event_fixtures(db):
    user = User(
        id=str(uuid4()),
        username=f"ag_evt_user_{uuid4().hex[:8]}",
        email=f"agevt_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()

    # PullRequestService resolves human PR authors through Actor.
    # Create the corresponding human Actor explicitly.
    user_actor = Actor(
        id=user.id,
        owner_id=user.id,
        type="human",
        name=user.username,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create"]'
        ),
    )
    db.add(user_actor)
    db.flush()

    repo = RepositoryService(db).create(
        owner_id=user.id,
        name=f"ag_evt_repo_{uuid4().hex[:8]}",
        description="Agent Event Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="evt_agent",
        token_prefix="prefix_agevt_123",
        token_hash="hash",
        is_active=True,
        status="active",
    )
    db.add(agent)

    actor = Actor(
        id=agent.id,
        owner_id=user.id,
        type="agent",
        name=agent.name,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create"]'
        ),
    )
    db.add(actor)
    db.commit()

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Agent Event Change",
        risk_level="low",
        resulting_commit="1111111111111111111111111111111111111111",
        base_commit="0000000000000000000000000000000000000000",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change)
    db.commit()

    svc = PullRequestService(db)

    pr = svc.create_pull_request(
        repo.id,
        user.id,
        change.id,
        "Agent Event PR",
        "main",
    )
    db.commit()

    return (
        user,
        repo,
        agent,
        actor,
        change,
        pr,
    )


def test_agent_audit_event_generation_and_sanitization(db):
    user, repo, agent, actor, change, pr = (
        setup_agent_event_fixtures(db)
    )

    svc = AgentReviewService(db)

    finding = svc.create_agent_finding(
        agent_id=agent.id,
        pull_request_id=pr.id,
        severity="medium",
        category="performance",
        message="Unoptimized loop detected",
        path="src/calc.py",
        line_number=30,
    )
    db.commit()

    events = db.scalars(
        select(ChangeEvent)
        .where(
            ChangeEvent.change_id == change.id,
            ChangeEvent.event_type
            == "agent_review.finding_created",
        )
    ).all()

    assert len(events) == 1

    ev = events[0]

    assert ev.actor_id == agent.id
    assert "performance" in ev.metadata_json
    assert "token" not in ev.metadata_json.lower()


def test_agent_audit_event_rollback_atomicity(db):
    user, repo, agent, actor, change, pr = (
        setup_agent_event_fixtures(db)
    )

    svc = AgentReviewService(db)

    svc.create_agent_comment(
        agent_id=agent.id,
        pull_request_id=pr.id,
        body="Uncommitted agent comment",
    )

    db.rollback()

    comments = db.scalars(
        select(InlineReviewComment)
        .where(
            InlineReviewComment.pull_request_id == pr.id
        )
    ).all()

    assert len(comments) == 0

    events = db.scalars(
        select(ChangeEvent)
        .where(
            ChangeEvent.change_id == change.id,
            ChangeEvent.event_type
            == "agent_review.comment_created",
        )
    ).all()

    assert len(events) == 0