from uuid import uuid4

from sqlalchemy import select

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.inline_review_comment import InlineReviewComment
from app.models.user import User
from app.services.pull_request_service import (
    PullRequestService,
)
from app.services.repository_service import (
    RepositoryService,
)


def setup_model_fixtures(db):
    user = User(
        id=str(uuid4()),
        username=f"model_user_{uuid4().hex[:8]}",
        email=f"muser_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    db.add(user)
    db.flush()

    # PullRequestService resolves the PR author through Actor.
    user_actor = Actor(
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

    db.add(user_actor)
    db.flush()

    repo = RepositoryService(db).create(
        owner_id=user.id,
        name=f"model_repo_{uuid4().hex[:8]}",
        description="Model Test Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="model_agent",
        token_prefix="prefix_model_123",
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
        intent="Model Change",
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

    db.add(change)
    db.commit()

    svc = PullRequestService(db)

    pr = svc.create_pull_request(
        repo.id,
        user.id,
        change.id,
        "Model PR",
        "main",
    )

    db.commit()

    return user, repo, change, pr


def test_create_general_comment_model(db):
    user, repo, change, pr = setup_model_fixtures(db)

    comment = InlineReviewComment(
        pull_request_id=pr.id,
        repository_id=repo.id,
        author_id=user.id,
        body="This is a general PR comment.",
    )

    db.add(comment)
    db.commit()

    saved = db.scalar(
        select(InlineReviewComment).where(
            InlineReviewComment.id == comment.id
        )
    )

    assert saved is not None
    assert saved.pull_request_id == pr.id
    assert saved.author_id == user.id
    assert saved.path is None
    assert saved.line_number is None
    assert (
        saved.status
        == InlineReviewComment.STATUS_ACTIVE
    )


def test_create_inline_comment_and_reply_model(db):
    user, repo, change, pr = setup_model_fixtures(db)

    root_comment = InlineReviewComment(
        pull_request_id=pr.id,
        repository_id=repo.id,
        author_id=user.id,
        path="src/main.py",
        diff_side="RIGHT",
        line_number=42,
        commit_sha=change.resulting_commit,
        body="Please refactor this line.",
    )

    db.add(root_comment)
    db.commit()

    reply_comment = InlineReviewComment(
        pull_request_id=pr.id,
        repository_id=repo.id,
        author_id=user.id,
        parent_id=root_comment.id,
        path="src/main.py",
        diff_side="RIGHT",
        line_number=42,
        commit_sha=change.resulting_commit,
        body="Done in next commit.",
    )

    db.add(reply_comment)
    db.commit()

    saved_reply = db.scalar(
        select(InlineReviewComment).where(
            InlineReviewComment.id
            == reply_comment.id
        )
    )

    assert saved_reply is not None
    assert (
        saved_reply.parent_id
        == root_comment.id
    )