from datetime import datetime, timezone
from pathlib import Path
import subprocess
from uuid import uuid4
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.models.user import User
from app.services.git_merge_service import GitMergeService
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService
from app.services.task_service import TaskService
from tests.conftest import ensure_test_actor


def setup_real_git_merge_fixtures(db):
    user_author = User(
        id=str(uuid4()),
        username=f"gmerge_author_{uuid4().hex[:8]}",
        email=f"gmergeauthor_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    user_reviewer = User(
        id=str(uuid4()),
        username=f"gmerge_reviewer_{uuid4().hex[:8]}",
        email=f"gmergereviewer_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add_all([user_author, user_reviewer])
    db.flush()

    ensure_test_actor(db, user_author)
    ensure_test_actor(db, user_reviewer)

    repo = RepositoryService(db).create(
        owner_id=user_author.id,
        name=f"gmerge_repo_{uuid4().hex[:8]}",
        description="Real Git Merge Repo",
        visibility="private",
    )

    repo_dir = Path(settings.repository_storage_path) / repo.storage_key

    # Initialize a commit on main branch inside the bare repo
    # Create initial commit using git commit-tree
    res_tree = subprocess.run(
        ["git", "--git-dir", str(repo_dir), "mktree"],
        input="",
        capture_output=True,
        text=True,
        check=True,
    )
    empty_tree = res_tree.stdout.strip()

    res_commit1 = subprocess.run(
        ["git", "--git-dir", str(repo_dir), "commit-tree", empty_tree, "-m", "Initial commit on main"],
        capture_output=True,
        text=True,
        check=True,
    )
    init_commit = res_commit1.stdout.strip()

    # Update main branch ref
    subprocess.run(
        ["git", "--git-dir", str(repo_dir), "update-ref", "refs/heads/main", init_commit],
        check=True,
    )

    # Create feature commit with parent init_commit
    res_commit2 = subprocess.run(
        ["git", "--git-dir", str(repo_dir), "commit-tree", empty_tree, "-p", init_commit, "-m", "Feature commit"],
        capture_output=True,
        text=True,
        check=True,
    )
    feature_commit = res_commit2.stdout.strip()

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=user_author.id,
        intent="Real Git Merge Feature",
        risk_level="low",
        resulting_commit=feature_commit,
        base_commit=init_commit,
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change)
    db.flush()

    # Create ChangeReview approved by reviewer
    review = ChangeReview(
        id=str(uuid4()),
        change_id=change.id,
        requested_by=user_author.id,
        reviewer_id=user_reviewer.id,
        status="approved",
        reason="Approved for real Git merge",
    )
    db.add(review)
    db.commit()

    return user_author, user_reviewer, repo, change, init_commit, feature_commit


def test_real_server_side_git_merge_execution(db):
    user_author, user_reviewer, repo, change, init_commit, feature_commit = setup_real_git_merge_fixtures(db)
    pr_svc = PullRequestService(db)

    # 1. Create PR
    pr = pr_svc.create_pull_request(
        repository_id=repo.id,
        author_id=user_author.id,
        source_change_id=change.id,
        title="Merge Feature PR",
        target_branch="main",
    )
    assert pr.status == PullRequest.STATUS_OPEN

    # 2. Approve PR
    pr_svc.approve_pull_request(pr, approver_id=user_reviewer.id, reason="Looks great")
    assert pr.status == PullRequest.STATUS_APPROVED

    # 3. Merge PR via real server-side Git merge transport
    res = pr_svc.merge_pull_request(pr.id, merger_id=user_author.id)
    db.commit()

    assert res.status == "merged"
    assert pr.status == PullRequest.STATUS_MERGED
    assert pr.target_commit == feature_commit
    assert pr.merged_at is not None

    # Verify Git ref actually updated to resulting commit
    repo_dir = Path(settings.repository_storage_path) / repo.storage_key
    ref_sha = GitMergeService().get_branch_ref(repo_dir, "main")
    assert ref_sha == feature_commit
    assert pr.target_commit == ref_sha


def test_real_git_merge_cas_conflict_prevention(db):
    user_author, user_reviewer, repo, change, init_commit, feature_commit = setup_real_git_merge_fixtures(db)
    repo_dir = Path(settings.repository_storage_path) / repo.storage_key
    svc = GitMergeService()

    # Create stale commit for main branch
    stale_sha = init_commit

    # Update main branch to feature_commit directly
    subprocess.run(
        ["git", "--git-dir", str(repo_dir), "update-ref", "refs/heads/main", feature_commit],
        check=True,
    )

    # Directly execute update-ref with stale_sha as expected -> CAS fails
    res_cas = svc._run_git(
        repo_dir,
        ["update-ref", "refs/heads/main", init_commit, stale_sha],
    )
    assert res_cas.returncode != 0
    assert "cannot lock ref" in res_cas.stderr or res_cas.returncode > 0


def test_task_completion_on_verified_git_merge(db):
    user_author, user_reviewer, repo, change, init_commit, feature_commit = setup_real_git_merge_fixtures(db)
    task_svc = TaskService(db)

    # 1. Create Task
    task = task_svc.create_task(
        repository_id=repo.id,
        created_by_id=user_author.id,
        title="Task linked to PR",
    )

    # Link Change & PR to Task
    task.resulting_change_id = change.id
    pr_svc = PullRequestService(db)
    pr = pr_svc.create_pull_request(
        repository_id=repo.id,
        author_id=user_author.id,
        source_change_id=change.id,
        title="PR for Linked Task",
        target_branch="main",
    )
    task.resulting_pull_request_id = pr.id
    task.status = Task.STATUS_IN_PROGRESS
    db.commit()

    assert task.status == Task.STATUS_IN_PROGRESS

    # 2. Approve PR
    pr_svc.approve_pull_request(pr, approver_id=user_reviewer.id)

    # 3. Merge PR
    res = pr_svc.merge_pull_request(pr.id, merger_id=user_author.id)
    db.commit()

    assert res.status == "merged"
    assert pr.status == PullRequest.STATUS_MERGED
    assert pr.target_commit == feature_commit

    # 4. Assert linked Task is now COMPLETED
    assert task.status == Task.STATUS_COMPLETED
    assert task.completed_at is not None

    events = db.scalars(
        select(TaskEvent)
        .where(TaskEvent.task_id == task.id)
        .order_by(TaskEvent.created_at.asc())
    ).all()

    completion_events = [
        event
        for event in events
        if event.event_type == TaskEvent.EVENT_COMPLETED
    ]

    assert len(completion_events) == 1

    completion_event = completion_events[0]

    assert completion_event.actor_id == user_author.id
    assert completion_event.from_status == Task.STATUS_IN_PROGRESS
    assert completion_event.to_status == Task.STATUS_COMPLETED

    # Verify PR-merge event
    change_events = db.scalars(
        select(ChangeEvent)
        .where(ChangeEvent.change_id == change.id)
        .order_by(ChangeEvent.created_at.asc())
    ).all()

    merge_events = [
        event
        for event in change_events
        if event.event_type == "pull_request.merged"
    ]
    assert len(merge_events) == 1
    assert merge_events[0].actor_id == user_author.id
    assert merge_events[0].to_status == PullRequest.STATUS_MERGED


def test_commit_tree_parent_ordering_and_correctness(db):
    user_author, user_reviewer, repo, change, init_commit, feature_commit = setup_real_git_merge_fixtures(db)
    repo_dir = Path(settings.repository_storage_path) / repo.storage_key
    svc = GitMergeService()

    # Create a non-fast-forward commit on target branch main so 3-way merge is triggered
    res_tree = svc._run_git(repo_dir, ["rev-parse", "HEAD^{tree}"])
    tree_sha = res_tree.stdout.strip()
    res_main_commit = svc._run_git(repo_dir, ["commit-tree", tree_sha, "-p", init_commit, "-m", "Divergent main commit"])
    divergent_main_commit = res_main_commit.stdout.strip()
    svc._run_git(repo_dir, ["update-ref", "refs/heads/main", divergent_main_commit])

    # Perform server-side merge
    res = svc.execute_server_side_merge(
        repository_storage_key=repo.storage_key,
        target_branch="main",
        source_commit=feature_commit,
        merger_id=user_author.id,
        commit_message="Test parent ordering commit-tree",
    )
    assert res.success is True
    assert res.is_fast_forward is False

    # Inspect commit object using git cat-file -p <resulting_commit>
    res_cat = svc._run_git(repo_dir, ["cat-file", "-p", res.resulting_commit])
    assert res_cat.returncode == 0
    lines = res_cat.stdout.splitlines()

    # First parent MUST be divergent_main_commit (previous target commit)
    # Second parent MUST be feature_commit (source commit)
    parents = [l.split()[1] for l in lines if l.startswith("parent ")]
    assert len(parents) == 2
    assert parents[0] == divergent_main_commit
    assert parents[1] == feature_commit


def test_git_db_consistency_rollback_and_reconciliation(db):
    user_author, user_reviewer, repo, change, init_commit, feature_commit = setup_real_git_merge_fixtures(db)
    pr_svc = PullRequestService(db)

    pr = pr_svc.create_pull_request(
        repository_id=repo.id,
        author_id=user_author.id,
        source_change_id=change.id,
        title="Reconciliation PR",
        target_branch="main",
    )
    pr_svc.approve_pull_request(pr, approver_id=user_reviewer.id)
    db.commit()

    # 1. Execute Git ref update manually to simulate Git ref mutation followed by DB failure
    repo_dir = Path(settings.repository_storage_path) / repo.storage_key
    svc = GitMergeService()
    svc._run_git(repo_dir, ["update-ref", "refs/heads/main", feature_commit, init_commit])

    # 2. PR status in DB is still APPROVED (unfinalized due to prior simulated DB crash)
    assert pr.status == PullRequest.STATUS_APPROVED

    # 3. Trigger merge_pull_request() again -> reconciles idempotently because Git ref is already at target
    res_recon = pr_svc.merge_pull_request(pr.id, merger_id=user_author.id)
    db.commit()

    assert res_recon.status == "merged"
    assert pr.status == PullRequest.STATUS_MERGED
    assert pr.target_commit == feature_commit
    assert pr.merged_at is not None


def test_git_merge_security_adversarial_validation(db):
    svc = GitMergeService()
    repo_dir = Path(settings.repository_storage_path) / "dummy"

    # 1. Branch traversal attempt
    with pytest.raises(ValueError, match="Dangerous Git branch name pattern denied"):
        svc.validate_branch_name("../main")

    # 2. Leading slash branch injection attempt
    with pytest.raises(ValueError, match="Dangerous Git branch name pattern denied"):
        svc.validate_branch_name("/etc/passwd")

    # 3. Invalid SHA validation
    with pytest.raises(ValueError, match="Invalid Git commit SHA"):
        svc.validate_commit_sha("12345")


def test_task_completion_idempotency(db):
    user_author, user_reviewer, repo, change, init_commit, feature_commit = setup_real_git_merge_fixtures(db)
    task_svc = TaskService(db)

    # 1. Create Task
    task = task_svc.create_task(
        repository_id=repo.id,
        created_by_id=user_author.id,
        title="Task for Idempotency Test",
    )

    # Link Change & PR to Task
    task.resulting_change_id = change.id
    pr_svc = PullRequestService(db)
    pr = pr_svc.create_pull_request(
        repository_id=repo.id,
        author_id=user_author.id,
        source_change_id=change.id,
        title="PR for Idempotency",
        target_branch="main",
    )
    task.resulting_pull_request_id = pr.id
    task.status = Task.STATUS_IN_PROGRESS
    db.commit()

    # Complete it first time using TaskService
    task_svc.complete_task(task.id, actor_id=user_author.id)
    db.commit()

    assert task.status == Task.STATUS_COMPLETED

    # Try completing again using TaskService
    task_svc.complete_task(task.id, actor_id=user_author.id)
    db.commit()

    # Invariant: status is still completed, and there is exactly one completion event
    assert task.status == Task.STATUS_COMPLETED

    events = db.scalars(
        select(TaskEvent)
        .where(TaskEvent.task_id == task.id)
        .order_by(TaskEvent.created_at.asc())
    ).all()

    completion_events = [
        event
        for event in events
        if event.event_type == TaskEvent.EVENT_COMPLETED
    ]
    assert len(completion_events) == 1


# ==============================================================================
# MERGE INTEGRITY REGRESSION TESTS (TESTS A - G)
# ==============================================================================


def test_successful_fast_forward_merge_target_commit_persistence(db):
    """TEST A: Fast-forward merge persists target_commit, updates PR and Change status, and updates Git ref."""
    user_author, user_reviewer, repo, change, init_commit, feature_commit = setup_real_git_merge_fixtures(db)
    pr_svc = PullRequestService(db)

    pr = pr_svc.create_pull_request(
        repository_id=repo.id,
        author_id=user_author.id,
        source_change_id=change.id,
        title="Fast Forward PR",
        target_branch="main",
    )
    pr_svc.approve_pull_request(pr, approver_id=user_reviewer.id)
    db.commit()

    res = pr_svc.merge_pull_request(pr.id, merger_id=user_author.id)
    db.commit()

    assert res.status == "merged"
    assert pr.status == PullRequest.STATUS_MERGED
    assert pr.target_commit == feature_commit
    assert pr.merged_at is not None
    assert change.status == "recorded"

    repo_dir = Path(settings.repository_storage_path) / repo.storage_key
    ref_sha = GitMergeService().get_branch_ref(repo_dir, "main")
    assert ref_sha == feature_commit
    assert pr.target_commit == ref_sha


def test_successful_three_way_merge_target_commit_persistence(db):
    """TEST B: 3-way merge persists generated merge commit SHA as target_commit, updates PR and Change."""
    user_author, user_reviewer, repo, change, init_commit, feature_commit = setup_real_git_merge_fixtures(db)
    repo_dir = Path(settings.repository_storage_path) / repo.storage_key
    svc = GitMergeService()

    # Diverge main branch
    res_tree = svc._run_git(repo_dir, ["rev-parse", "HEAD^{tree}"])
    tree_sha = res_tree.stdout.strip()
    res_main_commit = svc._run_git(repo_dir, ["commit-tree", tree_sha, "-p", init_commit, "-m", "Divergent main commit"])
    divergent_main_commit = res_main_commit.stdout.strip()
    svc._run_git(repo_dir, ["update-ref", "refs/heads/main", divergent_main_commit])

    pr_svc = PullRequestService(db)
    pr = pr_svc.create_pull_request(
        repository_id=repo.id,
        author_id=user_author.id,
        source_change_id=change.id,
        title="Three-Way PR",
        target_branch="main",
    )
    pr_svc.approve_pull_request(pr, approver_id=user_reviewer.id)
    db.commit()

    res = pr_svc.merge_pull_request(pr.id, merger_id=user_author.id)
    db.commit()

    assert res.status == "merged"
    assert pr.status == PullRequest.STATUS_MERGED
    assert pr.target_commit is not None
    assert len(pr.target_commit) == 40
    assert pr.target_commit != feature_commit
    assert pr.target_commit != divergent_main_commit
    assert pr.merged_at is not None
    assert change.status == "recorded"

    ref_sha = svc.get_branch_ref(repo_dir, "main")
    assert ref_sha == pr.target_commit


def test_git_merge_failure_prevents_pr_merge_and_change_finalization(db, monkeypatch):
    """TEST C: Forced GitMergeService failure leaves PR unmerged, target_commit null, change proposed."""
    user_author, user_reviewer, repo, change, init_commit, feature_commit = setup_real_git_merge_fixtures(db)
    pr_svc = PullRequestService(db)

    pr = pr_svc.create_pull_request(
        repository_id=repo.id,
        author_id=user_author.id,
        source_change_id=change.id,
        title="Failing Git PR",
        target_branch="main",
    )
    pr_svc.approve_pull_request(pr, approver_id=user_reviewer.id)
    db.commit()

    def fake_merge(*args, **kwargs):
        raise RuntimeError("Simulated Git transport I/O crash")

    monkeypatch.setattr(GitMergeService, "execute_server_side_merge", fake_merge)

    with pytest.raises(RuntimeError, match="Simulated Git transport I/O crash"):
        pr_svc.merge_pull_request(pr.id, merger_id=user_author.id)

    db.rollback()

    db.refresh(pr)
    db.refresh(change)
    assert pr.status == PullRequest.STATUS_APPROVED
    assert pr.target_commit is None
    assert pr.merged_at is None
    assert change.status == "proposed"


def test_post_update_verification_failure_leaves_pr_unmerged(db, monkeypatch):
    """TEST D: Post-update verification failure leaves PR unmerged."""
    user_author, user_reviewer, repo, change, init_commit, feature_commit = setup_real_git_merge_fixtures(db)
    pr_svc = PullRequestService(db)

    pr = pr_svc.create_pull_request(
        repository_id=repo.id,
        author_id=user_author.id,
        source_change_id=change.id,
        title="Post Update Fail PR",
        target_branch="main",
    )
    pr_svc.approve_pull_request(pr, approver_id=user_reviewer.id)
    db.commit()

    # Simulate get_branch_ref mismatch during post-update verification
    orig_get_ref = GitMergeService.get_branch_ref
    calls = [0]
    def fake_get_branch_ref(self, repo_path, branch_name):
        calls[0] += 1
        if calls[0] > 1:
            return "0000000000000000000000000000000000000000"
        return orig_get_ref(self, repo_path, branch_name)

    monkeypatch.setattr(GitMergeService, "get_branch_ref", fake_get_branch_ref)

    with pytest.raises(RuntimeError, match="Post-update verification failed"):
        pr_svc.merge_pull_request(pr.id, merger_id=user_author.id)

    db.rollback()
    db.refresh(pr)
    db.refresh(change)
    assert pr.status == PullRequest.STATUS_APPROVED
    assert pr.target_commit is None
    assert change.status == "proposed"


def test_missing_source_commit_strictly_fails_no_synthetic_commit(db):
    """TEST E: Attempting merge with nonexistent source commit fails strictly without synthetic commits."""
    user_author, user_reviewer, repo, change, init_commit, feature_commit = setup_real_git_merge_fixtures(db)
    svc = GitMergeService()

    fake_sha = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    with pytest.raises(ValueError, match="does not exist in repository"):
        svc.execute_server_side_merge(
            repository_storage_key=repo.storage_key,
            target_branch="main",
            source_commit=fake_sha,
            merger_id=user_author.id,
        )


def test_target_commit_api_response(db, client):
    """TEST F: Merged PR returns status='merged' and target_commit=actual SHA via GET /v1/pull-requests/{id}."""
    from app.core.security import create_access_token
    user_author, user_reviewer, repo, change, init_commit, feature_commit = setup_real_git_merge_fixtures(db)
    pr_svc = PullRequestService(db)

    pr = pr_svc.create_pull_request(
        repository_id=repo.id,
        author_id=user_author.id,
        source_change_id=change.id,
        title="API PR",
        target_branch="main",
    )
    pr_svc.approve_pull_request(pr, approver_id=user_reviewer.id)
    db.commit()

    token = create_access_token(subject=user_author.id)
    headers = {"Authorization": f"Bearer {token}"}

    # Merge via API
    res_merge = client.post(f"/v1/pull-requests/{pr.id}/merge", headers=headers)
    assert res_merge.status_code == 200

    # Get PR via API
    res_get = client.get(f"/v1/pull-requests/{pr.id}", headers=headers)
    assert res_get.status_code == 200
    pr_data = res_get.json()
    assert pr_data["status"] == "merged"
    assert pr_data["target_commit"] == feature_commit


def test_real_git_ref_consistency_with_target_commit(db):
    """TEST G: Verify refs/heads/main matches pr.target_commit on real Git repository."""
    user_author, user_reviewer, repo, change, init_commit, feature_commit = setup_real_git_merge_fixtures(db)
    pr_svc = PullRequestService(db)

    pr = pr_svc.create_pull_request(
        repository_id=repo.id,
        author_id=user_author.id,
        source_change_id=change.id,
        title="Ref Consistency PR",
        target_branch="main",
    )
    pr_svc.approve_pull_request(pr, approver_id=user_reviewer.id)
    db.commit()

    res = pr_svc.merge_pull_request(pr.id, merger_id=user_author.id)
    db.commit()

    repo_dir = Path(settings.repository_storage_path) / repo.storage_key
    ref_sha = GitMergeService().get_branch_ref(repo_dir, "main")

    assert pr.target_commit is not None
    assert ref_sha == pr.target_commit
    assert res.status == "merged"

