from uuid import uuid4

from sqlalchemy import select

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_event import ChangeEvent
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


def setup_event_fixtures(db):
    user = User(
        id=str(uuid4()),
        username=f"event_user_{uuid4().hex[:8]}",
        email=f"evt_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    db.add(user)
    db.flush()

    # PullRequestService and InlineReviewService use Actor identities.
    # Create the human Actor explicitly.
    _create_human_actor(
        db,
        user,
    )

    repo = RepositoryService(db).create(
        owner_id=user.id,
        name=f"event_repo_{uuid4().hex[:8]}",
        description="Event Test Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="event_agent",
        token_prefix="prefix_evt_123",
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
        intent="Event Change",
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
        "Event PR",
        "main",
    )

    db.commit()

    return (
        user,
        repo,
        change,
        pr,
    )


def test_inline_review_audit_events_creation_and_sanitization(
    db,
):
    user, repo, change, pr = setup_event_fixtures(
        db
    )

    svc = InlineReviewService(db)

    # 1. Create comment.
    c1 = svc.create_comment(
        pull_request_id=pr.id,
        author_id=user.id,
        body="Audit comment",
        path="src/main.py",
        diff_side="RIGHT",
        line_number=5,
    )

    db.commit()

    events = db.scalars(
        select(ChangeEvent)
        .where(
            ChangeEvent.change_id == change.id,
            ChangeEvent.event_type
            == "inline_review.comment_created",
        )
    ).all()

    assert len(events) == 1

    ev = events[0]

    assert ev.actor_id == user.id
    assert ev.to_status == "active"
    assert "token" not in ev.metadata_json.lower()

    # 2. Reply to comment.
    r1 = svc.create_comment(
        pull_request_id=pr.id,
        author_id=user.id,
        body="Audit reply",
        parent_id=c1.id,
    )

    db.commit()

    reply_events = db.scalars(
        select(ChangeEvent)
        .where(
            ChangeEvent.change_id == change.id,
            ChangeEvent.event_type
            == "inline_review.reply_created",
        )
    ).all()

    assert len(reply_events) == 1

    # 3. Resolve thread.
    svc.resolve_thread(
        c1.id,
        user.id,
    )

    db.commit()

    resolve_events = db.scalars(
        select(ChangeEvent)
        .where(
            ChangeEvent.change_id == change.id,
            ChangeEvent.event_type
            == "inline_review.thread_resolved",
        )
    ).all()

    assert len(resolve_events) == 1

    # 4. Reopen thread.
    svc.reopen_thread(
        c1.id,
        user.id,
    )

    db.commit()

    reopen_events = db.scalars(
        select(ChangeEvent)
        .where(
            ChangeEvent.change_id == change.id,
            ChangeEvent.event_type
            == "inline_review.thread_reopened",
        )
    ).all()

    assert len(reopen_events) == 1


def test_audit_event_transactional_rollback(
    db,
):
    user, repo, change, pr = setup_event_fixtures(
        db
    )

    svc = InlineReviewService(db)

    # Perform action inside an uncommitted session.
    svc.create_comment(
        pull_request_id=pr.id,
        author_id=user.id,
        body="Uncommitted comment",
    )

    db.rollback()

    comments = db.scalars(
        select(InlineReviewComment).where(
            InlineReviewComment.pull_request_id
            == pr.id
        )
    ).all()

    assert len(comments) == 0

    events = db.scalars(
        select(ChangeEvent)
        .where(
            ChangeEvent.change_id == change.id,
            ChangeEvent.event_type
            == "inline_review.comment_created",
        )
    ).all()

    assert len(events) == 0
    