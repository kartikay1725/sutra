from uuid import uuid4

import pytest

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.inline_review_comment import InlineReviewComment
from app.models.user import User
from app.services.inline_review_service import (
    InlineReviewService,
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


def setup_service_fixtures(db):
    user_a = User(
        id=str(uuid4()),
        username=f"svc_user_a_{uuid4().hex[:8]}",
        email=f"svca_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    user_b = User(
        id=str(uuid4()),
        username=f"svc_user_b_{uuid4().hex[:8]}",
        email=f"svcb_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    db.add_all(
        [
            user_a,
            user_b,
        ]
    )
    db.flush()

    # PullRequestService and InlineReviewService operate on Actor
    # identities. Create both human users explicitly.
    _create_human_actor(
        db,
        user_a,
    )

    _create_human_actor(
        db,
        user_b,
    )

    repo = RepositoryService(db).create(
        owner_id=user_a.id,
        name=f"svc_repo_{uuid4().hex[:8]}",
        description="Service Test Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user_a.id,
        name="svc_agent",
        token_prefix="prefix_svc_123",
        token_hash="hash",
        is_active=True,
        status="active",
    )

    db.add(agent)

    actor = Actor(
        id=agent.id,
        owner_id=user_a.id,
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
        intent="Service Change",
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
        user_a.id,
        change.id,
        "Service PR",
        "main",
    )

    db.commit()

    return (
        user_a,
        user_b,
        repo,
        change,
        pr,
    )


def test_create_general_and_inline_comments(db):
    (
        user_a,
        user_b,
        repo,
        change,
        pr,
    ) = setup_service_fixtures(db)

    svc = InlineReviewService(db)

    # Create general comment.
    c1 = svc.create_comment(
        pull_request_id=pr.id,
        author_id=user_a.id,
        body="General feedback for PR",
    )

    assert c1.path is None
    assert c1.line_number is None

    # Create inline comment.
    c2 = svc.create_comment(
        pull_request_id=pr.id,
        author_id=user_a.id,
        body="Inline comment on line 10",
        path="src/main.py",
        diff_side="RIGHT",
        line_number=10,
    )

    assert c2.path == "src/main.py"
    assert c2.line_number == 10
    assert c2.diff_side == "RIGHT"

    # Get comments.
    _, comments = svc.get_comments_for_pull_request(
        pr.id,
        user_a.id,
    )

    assert len(comments) == 2


def test_reply_and_resolve_thread_service(db):
    (
        user_a,
        user_b,
        repo,
        change,
        pr,
    ) = setup_service_fixtures(db)

    svc = InlineReviewService(db)

    root = svc.create_comment(
        pull_request_id=pr.id,
        author_id=user_a.id,
        body="Root issue",
        path="src/main.py",
        diff_side="RIGHT",
        line_number=15,
    )

    reply = svc.create_comment(
        pull_request_id=pr.id,
        author_id=user_a.id,
        body="Reply issue",
        parent_id=root.id,
    )

    assert reply.parent_id == root.id
    assert reply.path == "src/main.py"

    # Resolve thread using reply ID.
    resolved = svc.resolve_thread(
        reply.id,
        user_a.id,
    )

    assert resolved.id == root.id
    assert (
        resolved.status
        == InlineReviewComment.STATUS_RESOLVED
    )
    assert resolved.resolved_by == user_a.id

    # Reopen thread.
    reopened = svc.reopen_thread(
        root.id,
        user_a.id,
    )

    assert (
        reopened.status
        == InlineReviewComment.STATUS_ACTIVE
    )
    assert reopened.resolved_at is None


def test_service_validation_and_security(db):
    (
        user_a,
        user_b,
        repo,
        change,
        pr,
    ) = setup_service_fixtures(db)

    svc = InlineReviewService(db)

    # Empty body.
    with pytest.raises(
        ValueError,
        match="Comment body cannot be empty",
    ):
        svc.create_comment(
            pr.id,
            user_a.id,
            body="",
        )

    # Invalid path traversal.
    with pytest.raises(
        ValueError,
        match="Invalid file path",
    ):
        svc.create_comment(
            pr.id,
            user_a.id,
            body="Valid body",
            path="../../etc/passwd",
        )

    # Invalid line number.
    with pytest.raises(
        ValueError,
        match="line_number must be greater than 0",
    ):
        svc.create_comment(
            pr.id,
            user_a.id,
            body="Valid body",
            path="file.txt",
            line_number=0,
        )

    # Invalid side.
    with pytest.raises(
        ValueError,
        match="Invalid diff_side",
    ):
        svc.create_comment(
            pr.id,
            user_a.id,
            body="Valid body",
            path="file.txt",
            diff_side="CENTER",
        )

    # Private repository isolation:
    # User B has no access to User A's private repository.
    with pytest.raises(
        PermissionError,
        match="User does not have access",
    ):
        svc.create_comment(
            pr.id,
            user_b.id,
            body="Unauthorized comment",
        )