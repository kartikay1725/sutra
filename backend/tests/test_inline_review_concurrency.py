import concurrent.futures
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.inline_review_comment import InlineReviewComment
from app.models.pull_request import PullRequest
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


def setup_concurrency_fixtures():
    engine = create_engine(
        settings.database_url
    )
    SessionLocal = sessionmaker(
        bind=engine
    )
    db = SessionLocal()

    try:
        user = User(
            id=str(uuid4()),
            username=f"conc_user_{uuid4().hex[:8]}",
            email=f"conc_{uuid4().hex[:8]}@example.com",
            password_hash="hash",
        )

        db.add(user)
        db.flush()

        # The user is both the PR author and the author of
        # the root inline-review comment, so the corresponding
        # human Actor must exist explicitly.
        _create_human_actor(
            db,
            user,
        )

        repo = RepositoryService(db).create(
            owner_id=user.id,
            name=f"conc_repo_{uuid4().hex[:8]}",
            description="Concurrency Test Repo",
            visibility="private",
        )

        agent = Agent(
            id=str(uuid4()),
            owner_id=user.id,
            name="conc_agent",
            token_prefix="prefix_conc_123",
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
            intent="Concurrency Change",
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
            "Concurrency PR",
            "main",
        )

        db.commit()

        root_comment = InlineReviewService(
            db
        ).create_comment(
            pull_request_id=pr.id,
            author_id=user.id,
            body="Root thread for resolution race",
            path="src/app.py",
            diff_side="RIGHT",
            line_number=20,
        )

        db.commit()

        user_id = user.id
        pr_id = pr.id
        root_id = root_comment.id

        return (
            user_id,
            pr_id,
            root_id,
            SessionLocal,
        )

    finally:
        db.close()


def test_concurrent_comment_creation():
    (
        user_id,
        pr_id,
        root_id,
        SessionLocal,
    ) = setup_concurrency_fixtures()

    def worker_create(worker_idx: int):
        db = SessionLocal()

        try:
            svc = InlineReviewService(db)

            comment = svc.create_comment(
                pull_request_id=pr_id,
                author_id=user_id,
                body=f"Concurrent comment {worker_idx}",
                path="src/app.py",
                diff_side="RIGHT",
                line_number=worker_idx + 1,
            )

            db.commit()

            return comment.id

        finally:
            db.close()

    num_workers = 10

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=num_workers
    ) as executor:
        futures = [
            executor.submit(
                worker_create,
                i,
            )
            for i in range(num_workers)
        ]

        created_ids = [
            future.result()
            for future in concurrent.futures.as_completed(
                futures
            )
        ]

    assert len(created_ids) == num_workers

    db = SessionLocal()

    try:
        comments = db.scalars(
            select(InlineReviewComment).where(
                InlineReviewComment.pull_request_id
                == pr_id
            )
        ).all()

        # 1 root comment + 10 workers = 11 comments.
        assert len(comments) == 11

    finally:
        db.close()


def test_concurrent_thread_resolution():
    (
        user_id,
        pr_id,
        root_id,
        SessionLocal,
    ) = setup_concurrency_fixtures()

    def worker_resolve(worker_idx: int):
        db = SessionLocal()

        try:
            svc = InlineReviewService(db)

            comment = svc.resolve_thread(
                root_id,
                user_id,
            )

            db.commit()

            return comment.status

        finally:
            db.close()

    num_workers = 5

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=num_workers
    ) as executor:
        futures = [
            executor.submit(
                worker_resolve,
                i,
            )
            for i in range(num_workers)
        ]

        statuses = [
            future.result()
            for future in concurrent.futures.as_completed(
                futures
            )
        ]

    assert all(
        status == InlineReviewComment.STATUS_RESOLVED
        for status in statuses
    )

    db = SessionLocal()

    try:
        root = db.scalar(
            select(InlineReviewComment).where(
                InlineReviewComment.id == root_id
            )
        )

        assert root.status == (
            InlineReviewComment.STATUS_RESOLVED
        )
        assert root.resolved_by == user_id

    finally:
        db.close()