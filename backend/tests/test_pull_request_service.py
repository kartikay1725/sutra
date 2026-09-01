from datetime import datetime, timezone
from uuid import uuid4
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from pathlib import Path
import subprocess

from app.core.config import settings

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService
from tests.conftest import ensure_test_actor


def create_pr_service_fixtures(db: Session):
    user = User(
        id=str(uuid4()),
        username=f"svc_user_{uuid4().hex[:8]}",
        email=f"svc_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()

    ensure_test_actor(db, user)

    other_user = User(
        id=str(uuid4()),
        username=f"other_user_{uuid4().hex[:8]}",
        email=f"other_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(other_user)
    db.flush()

    ensure_test_actor(db, other_user)

    repo = RepositoryService(db).create(
        owner_id=user.id,
        name=f"svc_repo_{uuid4().hex[:8]}",
        description="Service test repo",
        visibility="private",
    )

    other_repo = RepositoryService(db).create(
        owner_id=other_user.id,
        name=f"other_repo_{uuid4().hex[:8]}",
        description="Other test repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="svc_agent",
        token_prefix="svc_prefix_1234",
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
            '["repository.read", "repository.write", "change.create"]'
        ),
    )
    db.add(actor)
    db.commit()

    # Use the real Git history created by RepositoryService.
    repo_dir = Path(settings.repository_storage_path) / repo.storage_key

    main_result = subprocess.run(
        [
            "git",
            "--git-dir",
            str(repo_dir),
            "rev-parse",
            "--verify",
            "refs/heads/main",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    base_commit = main_result.stdout.strip()

    # Create a real child commit so the Change's resulting_commit is
    # an actual commit in the repository and has a valid merge base.
    tree_result = subprocess.run(
        [
            "git",
            "--git-dir",
            str(repo_dir),
            "rev-parse",
            f"{base_commit}^{{tree}}",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    tree_sha = tree_result.stdout.strip()

    feature_result = subprocess.run(
        [
            "git",
            "--git-dir",
            str(repo_dir),
            "commit-tree",
            tree_sha,
            "-p",
            base_commit,
            "-m",
            "Service test change",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    feature_commit = feature_result.stdout.strip()

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Service Test Change",
        resulting_commit=feature_commit,
        base_commit=base_commit,
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change)
    db.commit()

    return (
        user,
        other_user,
        repo,
        other_repo,
        actor,
        change,
    )
def test_pr_valid_creation(db):
    user, other_user, repo, other_repo, actor, change = create_pr_service_fixtures(db)
    svc = PullRequestService(db)

    pr = svc.create_pull_request(
        repository_id=repo.id,
        author_id=user.id,
        source_change_id=change.id,
        title="Add awesome feature",
        target_branch="main",
        description="PR description",
    )

    assert pr.id is not None
    assert pr.status == PullRequest.STATUS_OPEN
    assert pr.title == "Add awesome feature"
    assert pr.target_branch == "main"
    assert pr.source_commit == change.resulting_commit


def test_pr_duplicate_source_change_id_idempotency(db):
    user, other_user, repo, other_repo, actor, change = create_pr_service_fixtures(db)
    svc = PullRequestService(db)

    pr1 = svc.create_pull_request(
        repository_id=repo.id,
        author_id=user.id,
        source_change_id=change.id,
        title="PR 1",
        target_branch="main",
    )

    # Creating again for the same source_change_id returns existing PR safely
    pr2 = svc.create_pull_request(
        repository_id=repo.id,
        author_id=user.id,
        source_change_id=change.id,
        title="PR 2",
        target_branch="main",
    )

    assert pr1.id == pr2.id


def test_pr_creation_validation_failures(db):
    user, other_user, repo, other_repo, actor, change = create_pr_service_fixtures(db)
    svc = PullRequestService(db)

    # Empty title
    with pytest.raises(ValueError, match="title cannot be empty"):
        svc.create_pull_request(repo.id, user.id, change.id, "", "main")

    # Empty target branch
    with pytest.raises(ValueError, match="Target branch cannot be empty"):
        svc.create_pull_request(repo.id, user.id, change.id, "Title", "")

    # Non-existent repo
    with pytest.raises(ValueError, match="Repository not found"):
        svc.create_pull_request(str(uuid4()), user.id, change.id, "Title", "main")

    # Non-existent author
    with pytest.raises(ValueError, match="Author user not found"):
        svc.create_pull_request(repo.id, str(uuid4()), change.id, "Title", "main")

    # Change / repository mismatch
    with pytest.raises(ValueError, match="Change does not belong to target repository"):
        svc.create_pull_request(other_repo.id, other_user.id, change.id, "Title", "main")

    # Unauthorized user
    with pytest.raises(PermissionError, match="Repository access denied"):
        svc.create_pull_request(repo.id, other_user.id, change.id, "Title", "main")


def test_pr_read_authorization_and_isolation(db):
    user, other_user, repo, other_repo, actor, change = create_pr_service_fixtures(db)
    svc = PullRequestService(db)

    pr = svc.create_pull_request(repo.id, user.id, change.id, "Title", "main")

    # Authorized user can get PR
    fetched = svc.get_pull_request(pr.id, user.id)
    assert fetched is not None
    assert fetched.id == pr.id

    # Other user gets None (no private repo resource enumeration)
    assert svc.get_pull_request(pr.id, other_user.id) is None


def test_pr_lifecycle_transitions(db):
    user, other_user, repo, other_repo, actor, change = create_pr_service_fixtures(db)
    svc = PullRequestService(db)

    pr = svc.create_pull_request(repo.id, user.id, change.id, "Title", "main")

    # Open -> Rejected -> Open -> Closed
    pr_rej = svc.reject_pull_request(pr, user.id)
    assert pr_rej.status == PullRequest.STATUS_REJECTED
    assert pr_rej.closed_at is not None

    pr_open = svc.transition_pull_request(pr_rej, PullRequest.STATUS_OPEN)
    assert pr_open.status == PullRequest.STATUS_OPEN

    pr_closed = svc.close_pull_request(pr_open, user.id)
    assert pr_closed.status == PullRequest.STATUS_CLOSED

    # Terminal state protection
    with pytest.raises(ValueError, match="Cannot transition"):
        svc.transition_pull_request(pr_closed, PullRequest.STATUS_OPEN)


def test_pr_approval_requires_change_review_and_no_self_review(db):
    user, other_user, repo, other_repo, actor, change = create_pr_service_fixtures(db)
    svc = PullRequestService(db)

    pr = svc.create_pull_request(repo.id, user.id, change.id, "Title", "main")

    # Approval without ChangeReview fails
    with pytest.raises(ValueError, match="An approved ChangeReview is required"):
        svc.approve_pull_request(pr, approver_id=other_user.id)

    # Self-approval by author is prohibited
    review_self = ChangeReview(
        change_id=change.id,
        requested_by=user.id,
        reviewer_id=user.id,
        status="approved",
    )
    db.add(review_self)
    db.commit()

    with pytest.raises(ValueError, match="Self-review approval is strictly prohibited"):
        svc.approve_pull_request(pr, approver_id=user.id)

    # Valid approval by other reviewer succeeds
    review_other = ChangeReview(
        change_id=change.id,
        requested_by=user.id,
        reviewer_id=other_user.id,
        status="approved",
    )
    db.add(review_other)
    db.commit()

    pr_approved = svc.approve_pull_request(pr, approver_id=other_user.id)
    assert pr_approved.status == PullRequest.STATUS_APPROVED


def test_pr_merge_validation_and_guarantees(db):
    user, other_user, repo, other_repo, actor, change = create_pr_service_fixtures(db)
    svc = PullRequestService(db)

    pr = svc.create_pull_request(repo.id, user.id, change.id, "Title", "main")

    # Approve PR first
    review = ChangeReview(
        change_id=change.id,
        requested_by=user.id,
        reviewer_id=other_user.id,
        status="approved",
    )
    db.add(review)
    db.commit()

    pr = svc.approve_pull_request(pr, approver_id=other_user.id)
    assert pr.status == PullRequest.STATUS_APPROVED

    # Unauthorized merger fails
    with pytest.raises(PermissionError, match="Repository access denied"):
        svc.merge_pull_request(pr, merger_id=other_user.id)

    # Merge precondition check succeeds for authorized repo owner
    result = svc.merge_pull_request(pr, merger_id=user.id)
    assert result.status in {"merged", "merge_ready"}
    assert result.pull_request.id == pr.id

    # Terminal state protection: merged PR cannot be re-opened
    assert pr.status == PullRequest.STATUS_MERGED
    assert pr.target_commit is not None
    assert len(pr.target_commit) == 40
    with pytest.raises(ValueError, match="Cannot transition"):
        svc.transition_pull_request(pr, PullRequest.STATUS_OPEN)


def test_pr_concurrent_creation_race_behavior_pg():
    import concurrent.futures
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        user, other_user, repo, other_repo, actor, change = create_pr_service_fixtures(db)
        repo_id = repo.id
        user_id = user.id
        change_id = change.id

    results = []
    errors = []

    def create_worker():
        session = SessionLocal()
        try:
            svc = PullRequestService(session)
            pr = svc.create_pull_request(
                repository_id=repo_id,
                author_id=user_id,
                source_change_id=change_id,
                title="Concurrent PR",
                target_branch="main",
            )
            session.commit()
            return pr.id
        except Exception as e:
            session.rollback()
            errors.append(str(e))
            return None
        finally:
            session.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(create_worker) for _ in range(5)]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                results.append(res)

    assert len(errors) == 0, f"Concurrent workers encountered errors: {errors}"
    assert len(results) == 5
    assert len(set(results)) == 1, "All concurrent workers must receive the exact same PullRequest ID"

    with SessionLocal() as db:
        prs = db.scalars(select(PullRequest).where(PullRequest.source_change_id == change_id)).all()
        assert len(prs) == 1, "Database must contain exactly 1 PullRequest"
