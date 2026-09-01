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
from app.services.authorization_service import AuthorizationService
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService


def setup_agent_model_fixtures(db):
    user = User(
        id=str(uuid4()),
        username=f"ag_user_{uuid4().hex[:8]}",
        email=f"aguser_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()

    # PullRequestService uses Actor as the authoritative identity for
    # pull-request authors. Create the human Actor explicitly instead of
    # relying on a global SQLAlchemy event hook.
    user_actor = Actor(
        id=user.id,
        owner_id=user.id,
        type="human",
        name=user.username,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create", '
            '"change.conflict.read"]'
        ),
    )
    db.add(user_actor)
    db.flush()

    repo = RepositoryService(db).create(
        owner_id=user.id,
        name=f"ag_repo_{uuid4().hex[:8]}",
        description="Agent Model Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="review_agent",
        token_prefix="prefix_ag_123",
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
            '"change.create", '
            '"change.conflict.read"]'
        ),
    )
    db.add(actor)
    db.commit()

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Agent Change",
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
        "Agent PR",
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


def test_agent_actor_model_capabilities(db):
    user, repo, agent, actor, change, pr = (
        setup_agent_model_fixtures(db)
    )

    # Verify actor capability parsing via AuthorizationService.
    caps = AuthorizationService._capabilities(actor)

    assert "repository.read" in caps
    assert "repository.write" in caps
    assert "change.create" in caps
    assert "change.conflict.read" in caps

    # Verify agent model relationship with user owner.
    saved_agent = db.scalar(
        select(Agent).where(
            Agent.id == agent.id
        )
    )

    assert saved_agent is not None
    assert saved_agent.owner_id == user.id
    assert saved_agent.status == "active"
    assert saved_agent.is_active is True


def test_agent_review_event_and_comment_representation(db):
    user, repo, agent, actor, change, pr = (
        setup_agent_model_fixtures(db)
    )

    # Test storing inline review comment for agent
    # using agent.owner_id as the user FK.
    comment = InlineReviewComment(
        pull_request_id=pr.id,
        repository_id=repo.id,
        author_id=user.id,
        path="src/utils.py",
        diff_side="RIGHT",
        line_number=15,
        body=(
            "[AGENT FINDING] "
            "Potential null pointer dereference."
        ),
    )

    db.add(comment)
    db.flush()

    # Record ChangeEvent attributed to the agent Actor ID.
    event = ChangeEvent(
        change_id=change.id,
        actor_id=actor.id,
        event_type="agent_review.finding_created",
        from_status=None,
        to_status="active",
        metadata_json=(
            f'{{"agent_id": "{agent.id}", '
            '"severity": "high", '
            '"category": "bug"}'
        ),
    )

    db.add(event)
    db.commit()

    saved_event = db.scalar(
        select(ChangeEvent).where(
            ChangeEvent.id == event.id
        )
    )

    assert saved_event is not None
    assert saved_event.actor_id == agent.id
    assert "high" in saved_event.metadata_json