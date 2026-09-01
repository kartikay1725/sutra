import concurrent.futures
import threading
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService


def _require_postgresql() -> None:
    """
    These tests validate PostgreSQL-specific concurrency semantics.

    Running them against SQLite would produce false results because SQLite
    does not provide the same row-locking/concurrency behavior as PostgreSQL.
    """
    if not settings.database_url.lower().startswith(
        ("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")
    ):
        pytest.skip(
            "PostgreSQL concurrency test skipped: "
            f"configured database is '{settings.database_url.split(':', 1)[0]}', "
            "not PostgreSQL."
        )


def setup_concurrency_fixtures():
    _require_postgresql()

    with SessionLocal() as db:
        author = User(
            id=str(uuid4()),
            username=f"conc_author_{uuid4().hex[:8]}",
            email=f"cauthor_{uuid4().hex[:8]}@example.com",
            password_hash="hash",
        )
        db.add(author)

        reviewer = User(
            id=str(uuid4()),
            username=f"conc_reviewer_{uuid4().hex[:8]}",
            email=f"creviewer_{uuid4().hex[:8]}@example.com",
            password_hash="hash",
        )
        db.add(reviewer)
        db.flush()

        repo = RepositoryService(db).create(
            owner_id=author.id,
            name=f"conc_repo_{uuid4().hex[:8]}",
            description="Concurrency Test Repo",
            visibility="private",
        )

        agent = Agent(
            id=str(uuid4()),
            owner_id=author.id,
            name="conc_agent",
            token_prefix=f"prefix_{uuid4().hex[:8]}",
            token_hash="hash",
            is_active=True,
            status="active",
        )
        db.add(agent)
        db.flush()

        actor = Actor(
            id=agent.id,
            owner_id=author.id,
            type="agent",
            name=agent.name,
            capabilities=(
                '["repository.read",'
                '"repository.write",'
                '"change.create"]'
            ),
        )
        db.add(actor)
        db.flush()

        db.commit()

        change = Change(
            id=str(uuid4()),
            repository_id=repo.id,
            actor_id=actor.id,
            intent="Concurrency Change",
            risk_level="low",
            resulting_commit="1111111111111111111111111111111111111111",
            base_commit="0000000000000000000000000000000000000000",
            operation_key=(uuid4().hex * 2)[:64],
            status="proposed",
        )
        db.add(change)
        db.commit()

        return (
            author.id,
            reviewer.id,
            repo.id,
            actor.id,
            change.id,
        )


def test_concurrent_same_change_pr_creation_race_pg():
    _require_postgresql()

    (
        author_id,
        reviewer_id,
        repo_id,
        actor_id,
        change_id,
    ) = setup_concurrency_fixtures()

    num_workers = 15

    def worker_task(worker_idx):
        with SessionLocal() as db:
            svc = PullRequestService(db)

            try:
                pr = svc.create_pull_request(
                    repository_id=repo_id,
                    author_id=author_id,
                    source_change_id=change_id,
                    title=f"Concurrent PR {worker_idx}",
                    target_branch="main",
                )

                db.commit()
                return pr.id

            except Exception as exc:
                db.rollback()

                # A legitimate concurrency loser may encounter an
                # IntegrityError/uniqueness race. The service is expected
                # to reconcile that race rather than crash the test process.
                return f"ERROR: {type(exc).__name__} - {exc}"

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=num_workers
    ) as executor:
        futures = [
            executor.submit(worker_task, i)
            for i in range(num_workers)
        ]

        results = [
            future.result()
            for future in concurrent.futures.as_completed(futures)
        ]

    errors = [
        result
        for result in results
        if str(result).startswith("ERROR:")
    ]

    assert not errors, (
        "Encountered unexpected errors during creation race: "
        f"{errors}"
    )

    pr_ids = set(results)

    assert len(pr_ids) == 1, (
        f"Expected 1 unique PR ID, got {len(pr_ids)}: {pr_ids}"
    )

    winning_pr_id = next(iter(pr_ids))

    with SessionLocal() as db:
        prs = db.scalars(
            select(PullRequest).where(
                PullRequest.id == winning_pr_id
            )
        ).all()

        assert len(prs) == 1

        all_change_prs = db.scalars(
            select(PullRequest).where(
                PullRequest.source_change_id == change_id
            )
        ).all()

        assert len(all_change_prs) == 1


def test_different_change_parallel_creation_pg():
    _require_postgresql()

    (
        author_id,
        reviewer_id,
        repo_id,
        actor_id,
        change_id,
    ) = setup_concurrency_fixtures()

    num_workers = 10

    def worker_task(worker_idx):
        with SessionLocal() as db:
            change = Change(
                id=str(uuid4()),
                repository_id=repo_id,
                actor_id=actor_id,
                intent=f"Parallel Change {worker_idx}",
                risk_level="low",
                resulting_commit=(
                    "2" * 39 + str(worker_idx % 10)
                ),
                base_commit="0" * 40,
                operation_key=(uuid4().hex * 2)[:64],
                status="proposed",
            )

            db.add(change)
            db.commit()

            svc = PullRequestService(db)

            try:
                pr = svc.create_pull_request(
                    repository_id=repo_id,
                    author_id=author_id,
                    source_change_id=change.id,
                    title=f"Parallel PR {worker_idx}",
                    target_branch="main",
                )

                db.commit()
                return pr.id

            except Exception as exc:
                db.rollback()
                return f"ERROR: {type(exc).__name__} - {exc}"

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=num_workers
    ) as executor:
        futures = [
            executor.submit(worker_task, i)
            for i in range(num_workers)
        ]

        results = [
            future.result()
            for future in concurrent.futures.as_completed(futures)
        ]

    errors = [
        result
        for result in results
        if str(result).startswith("ERROR:")
    ]

    assert not errors, (
        "Unexpected errors during independent parallel PR creation: "
        f"{errors}"
    )

    pr_ids = set(results)

    assert len(pr_ids) == num_workers


def test_concurrent_approval_pg():
    _require_postgresql()

    (
        author_id,
        reviewer_id,
        repo_id,
        actor_id,
        change_id,
    ) = setup_concurrency_fixtures()

    with SessionLocal() as db:
        svc = PullRequestService(db)

        pr = svc.create_pull_request(
            repository_id=repo_id,
            author_id=author_id,
            source_change_id=change_id,
            title="Concurrent Approval PR",
            target_branch="main",
        )
        db.flush()

        # A ChangeReview is required before PR approval. Create a pending one.
        svc.create_pull_request_review_request(
            pr=pr,
            requester_id=author_id,
        )

        db.commit()
        pr_id = pr.id

    def approve():
        with SessionLocal() as db:
            service = PullRequestService(db)

            try:
                # Fetch the PR object — approve_pull_request expects PullRequest, not str.
                pr_obj = db.scalar(
                    select(PullRequest).where(PullRequest.id == pr_id)
                )
                if pr_obj is None:
                    return "ValueError: PullRequest not found"

                result = service.approve_pull_request(
                    pr_obj,
                    approver_id=reviewer_id,
                )
                db.commit()
                return "OK"

            except Exception as exc:
                db.rollback()
                return f"{type(exc).__name__}: {exc}"

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=8
    ) as executor:
        results = list(
            executor.map(
                lambda _: approve(),
                range(8),
            )
        )

    unexpected = [
        result
        for result in results
        if result != "OK"
        and "already" not in result.lower()
        and "approved" not in result.lower()
        and "transition" not in result.lower()
    ]

    assert not unexpected, (
        "Unexpected concurrent approval errors: "
        f"{unexpected}"
    )

    with SessionLocal() as db:
        final_pr = db.scalar(
            select(PullRequest).where(
                PullRequest.id == pr_id
            )
        )

        assert final_pr is not None
        assert final_pr.status == PullRequest.STATUS_APPROVED


def test_concurrent_merge_orchestration_row_locking_pg():
    _require_postgresql()

    (
        author_id,
        reviewer_id,
        repo_id,
        actor_id,
        change_id,
    ) = setup_concurrency_fixtures()

    with SessionLocal() as db:
        svc = PullRequestService(db)

        pr = svc.create_pull_request(
            repository_id=repo_id,
            author_id=author_id,
            source_change_id=change_id,
            title="Concurrent Merge PR",
            target_branch="main",
        )
        db.flush()

        # A ChangeReview is required before PR approval. Create a pending one.
        svc.create_pull_request_review_request(
            pr=pr,
            requester_id=author_id,
        )
        db.flush()

        svc.approve_pull_request(
            pr,
            approver_id=reviewer_id,
        )

        db.commit()

        pr_id = pr.id

    def merge():
        with SessionLocal() as db:
            service = PullRequestService(db)

            try:
                result = service.merge_pull_request(
                    pr_id,
                    merger_id=author_id,
                )
                db.commit()

                return (
                    "OK",
                    result.status if result else None,
                )

            except Exception as exc:
                db.rollback()
                return (
                    type(exc).__name__,
                    str(exc),
                )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=4
    ) as executor:
        results = list(
            executor.map(
                lambda _: merge(),
                range(4),
            )
        )

    with SessionLocal() as db:
        final_pr = db.scalar(
            select(PullRequest).where(
                PullRequest.id == pr_id
            )
        )

        assert final_pr is not None
        assert final_pr.status == PullRequest.STATUS_MERGED


def test_transaction_rollback_atomicity():
    _require_postgresql()

    (
        author_id,
        reviewer_id,
        repo_id,
        actor_id,
        change_id,
    ) = setup_concurrency_fixtures()

    with SessionLocal() as db:
        svc = PullRequestService(db)

        pr = svc.create_pull_request(
            repository_id=repo_id,
            author_id=author_id,
            source_change_id=change_id,
            title="Rollback Atomicity PR",
            target_branch="main",
        )

        pr_id = pr.id

        db.rollback()

    with SessionLocal() as db:
        persisted = db.scalar(
            select(PullRequest).where(
                PullRequest.id == pr_id
            )
        )

        assert persisted is None


def test_database_uniqueness_enforcement():
    _require_postgresql()

    (
        author_id,
        reviewer_id,
        repo_id,
        actor_id,
        change_id,
    ) = setup_concurrency_fixtures()

    with SessionLocal() as db:
        svc = PullRequestService(db)

        first = svc.create_pull_request(
            repository_id=repo_id,
            author_id=author_id,
            source_change_id=change_id,
            title="Uniqueness PR",
            target_branch="main",
        )

        db.commit()

        first_id = first.id

    with SessionLocal() as db:
        try:
            duplicate = PullRequest(
                id=str(uuid4()),
                repository_id=repo_id,
                author_id=author_id,
                source_change_id=change_id,
                title="Duplicate Uniqueness PR",
                target_branch="main",
                status=PullRequest.STATUS_OPEN,
            )

            db.add(duplicate)
            db.commit()

            # If this succeeds, the application/database does not enforce
            # the intended uniqueness invariant.
            duplicate_succeeded = True

        except IntegrityError:
            db.rollback()
            duplicate_succeeded = False

        assert duplicate_succeeded is False


def test_pr_concurrent_creation_race_behavior_pg():
    _require_postgresql()

    (
        author_id,
        reviewer_id,
        repo_id,
        actor_id,
        change_id,
    ) = setup_concurrency_fixtures()

    barrier = threading.Barrier(2)

    results = []

    def worker(worker_idx):
        with SessionLocal() as db:
            svc = PullRequestService(db)

            try:
                barrier.wait(timeout=10)

                pr = svc.create_pull_request(
                    repository_id=repo_id,
                    author_id=author_id,
                    source_change_id=change_id,
                    title=f"Race PR {worker_idx}",
                    target_branch="main",
                )

                db.commit()

                return pr.id

            except Exception as exc:
                db.rollback()
                return f"ERROR: {type(exc).__name__}: {exc}"

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(worker, i)
            for i in range(2)
        ]

        results = [
            future.result()
            for future in futures
        ]

    errors = [
        result
        for result in results
        if str(result).startswith("ERROR:")
    ]

    assert not errors, (
        "Concurrent PR creation unexpectedly failed: "
        f"{errors}"
    )

    assert len(set(results)) == 1