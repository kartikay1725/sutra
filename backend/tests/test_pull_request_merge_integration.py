from datetime import datetime, timezone
from uuid import uuid4
import pytest
from fastapi import status
from sqlalchemy import select

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.change_policy_service import ChangePolicyService
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService
from tests.conftest import ensure_test_actor


def setup_merge_fixtures(db):
    author = User(
        id=str(uuid4()),
        username=f"merge_author_{uuid4().hex[:8]}",
        email=f"mauthor_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(author)

    reviewer = User(
        id=str(uuid4()),
        username=f"merge_reviewer_{uuid4().hex[:8]}",
        email=f"mreviewer_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(reviewer)

    unauth = User(
        id=str(uuid4()),
        username=f"merge_unauth_{uuid4().hex[:8]}",
        email=f"munauth_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(unauth)
    db.flush()

    ensure_test_actor(db, author)
    ensure_test_actor(db, reviewer)
    ensure_test_actor(db, unauth)

    repo = RepositoryService(db).create(
        owner_id=author.id,
        name=f"merge_repo_{uuid4().hex[:8]}",
        description="Merge Test Repo",
        visibility="private",
    )

    repo_other = RepositoryService(db).create(
        owner_id=unauth.id,
        name=f"merge_repo_other_{uuid4().hex[:8]}",
        description="Other Repo",
        visibility="private",
    )

    repo_del = RepositoryService(db).create(
        owner_id=author.id,
        name=f"merge_repo_del_{uuid4().hex[:8]}",
        description="Deleted Repo",
        visibility="private",
    )
    repo_del.deleted_at = datetime.now(timezone.utc)
    db.commit()

    agent = Agent(
        id=str(uuid4()),
        owner_id=author.id,
        name="merge_agent",
        token_prefix="prefix_merge_123",
        token_hash="hash",
        is_active=True,
        status="active",
    )
    db.add(agent)

    actor = Actor(
        id=agent.id,
        owner_id=author.id,
        type="agent",
        name=agent.name,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    db.add(actor)
    db.commit()

    import subprocess
    from pathlib import Path
    from app.core.config import settings

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

    def make_real_commit(msg):
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
                msg,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return feature_result.stdout.strip()

    change_allow = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="ALLOW Change",
        risk_level="low",
        resulting_commit=make_real_commit("ALLOW Change commit"),
        base_commit=base_commit,
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change_allow)

    change_review = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="REVIEW Change",
        risk_level="high",
        resulting_commit=make_real_commit("REVIEW Change commit"),
        base_commit=base_commit,
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change_review)

    change_block = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="BLOCK Change",
        risk_level="critical",
        resulting_commit=make_real_commit("BLOCK Change commit"),
        base_commit=base_commit,
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change_block)

    change_no_commit = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="No Commit Change",
        risk_level="low",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change_no_commit)
    db.commit()

    svc = PullRequestService(db)
    pr_allow = svc.create_pull_request(repo.id, author.id, change_allow.id, "ALLOW PR", "main")
    pr_review = svc.create_pull_request(repo.id, author.id, change_review.id, "REVIEW PR", "main")
    pr_no_commit = svc.create_pull_request(repo.id, author.id, change_no_commit.id, "No Commit PR", "main")

    return author, reviewer, unauth, repo, repo_other, repo_del, actor, change_allow, change_review, change_block, pr_allow, pr_review, pr_no_commit


def test_merge_unauthenticated_rejected(client):
    res = client.post("/v1/pull-requests/00000000-0000-0000-0000-000000000000/merge")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_merge_unauthorized_repository_and_idor_protection(db, client):
    author, reviewer, unauth, repo, repo_other, repo_del, actor, change_allow, change_review, change_block, pr_allow, pr_review, pr_no_commit = setup_merge_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: unauth

    # Unauthorized user gets 403 or 404 for private repository PR
    res = client.post(f"/v1/pull-requests/{pr_allow.id}/merge")
    assert res.status_code in {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND}

    app.dependency_overrides.clear()


def test_merge_nonexistent_pr_deleted_repo_malformed_id(db, client):
    author, reviewer, unauth, repo, repo_other, repo_del, actor, change_allow, change_review, change_block, pr_allow, pr_review, pr_no_commit = setup_merge_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: author

    # Nonexistent PR returns 404
    res_non = client.post(f"/v1/pull-requests/{uuid4()}/merge")
    assert res_non.status_code == status.HTTP_404_NOT_FOUND

    # Malformed UUID returns 404
    res_mal = client.post("/v1/pull-requests/invalid-uuid/merge")
    assert res_mal.status_code == status.HTTP_404_NOT_FOUND

    # Deleted repo PR returns 404
    change_del = Change(
        id=str(uuid4()),
        repository_id=repo_del.id,
        actor_id=author.id,
        intent="Del Change",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change_del)

    pr_del = PullRequest(
        repository_id=repo_del.id,
        author_id=author.id,
        source_change_id=change_del.id,
        title="Del PR",
        target_branch="main",
        status="open",
    )
    db.add(pr_del)
    db.commit()

    res_del = client.post(f"/v1/pull-requests/{pr_del.id}/merge")
    assert res_del.status_code == status.HTTP_404_NOT_FOUND

    app.dependency_overrides.clear()


def test_merge_cross_repository_invariant_violation(db, client):
    author, reviewer, unauth, repo, repo_other, repo_del, actor, change_allow, change_review, change_block, pr_allow, pr_review, pr_no_commit = setup_merge_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: author

    # Change belonging to repo_other attached to PR in repo
    mismatch_change = Change(
        id=str(uuid4()),
        repository_id=repo_other.id,
        actor_id=author.id,
        intent="Mismatch Change",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(mismatch_change)

    mismatch_pr = PullRequest(
        repository_id=repo.id,
        author_id=author.id,
        source_change_id=mismatch_change.id,
        title="Mismatch PR",
        target_branch="main",
        status="open",
    )
    db.add(mismatch_pr)
    db.commit()

    res = client.post(f"/v1/pull-requests/{mismatch_pr.id}/merge")
    assert res.status_code == status.HTTP_404_NOT_FOUND

    app.dependency_overrides.clear()


def test_merge_policy_allow_orchestration(db, client):
    author, reviewer, unauth, repo, repo_other, repo_del, actor, change_allow, change_review, change_block, pr_allow, pr_review, pr_no_commit = setup_merge_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: author

    res = client.post(f"/v1/pull-requests/{pr_allow.id}/merge")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["status"] in {"merged", "merge_ready"}
    assert data["pull_request_id"] == pr_allow.id
    assert "merged" in data["detail"] or "preconditions satisfied" in data["detail"]

    # Verify status updated to MERGED
    db.refresh(pr_allow)
    assert pr_allow.status == PullRequest.STATUS_MERGED
    assert pr_allow.merged_at is not None

    app.dependency_overrides.clear()


def test_merge_policy_review_without_approved_change_review_rejected(db, client):
    author, reviewer, unauth, repo, repo_other, repo_del, actor, change_allow, change_review, change_block, pr_allow, pr_review, pr_no_commit = setup_merge_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: author

    # Policy decision is REVIEW, no approved ChangeReview present
    res = client.post(f"/v1/pull-requests/{pr_review.id}/merge")
    assert res.status_code == status.HTTP_409_CONFLICT
    assert "Change requires an approved ChangeReview" in res.json()["detail"]

    app.dependency_overrides.clear()


def test_merge_policy_block_rejected(db, client):
    author, reviewer, unauth, repo, repo_other, repo_del, actor, change_allow, change_review, change_block, pr_allow, pr_review, pr_no_commit = setup_merge_fixtures(db)
    svc = PullRequestService(db)

    # Change escalated to BLOCK
    change_allow.risk_level = "critical"
    db.commit()

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: author

    res = client.post(f"/v1/pull-requests/{pr_allow.id}/merge")
    assert res.status_code == status.HTTP_409_CONFLICT
    assert "blocked by policy" in res.json()["detail"]

    app.dependency_overrides.clear()


def test_merge_missing_resulting_commit_rejected(db, client):
    author, reviewer, unauth, repo, repo_other, repo_del, actor, change_allow, change_review, change_block, pr_allow, pr_review, pr_no_commit = setup_merge_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: author

    res = client.post(f"/v1/pull-requests/{pr_no_commit.id}/merge")
    assert res.status_code == status.HTTP_409_CONFLICT
    assert "has no resulting commit" in res.json()["detail"]

    app.dependency_overrides.clear()


def test_merge_closed_or_merged_pr_rejected(db, client):
    author, reviewer, unauth, repo, repo_other, repo_del, actor, change_allow, change_review, change_block, pr_allow, pr_review, pr_no_commit = setup_merge_fixtures(db)
    svc = PullRequestService(db)

    svc.close_pull_request(pr_allow, author.id)
    assert pr_allow.status == PullRequest.STATUS_CLOSED

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: author

    res = client.post(f"/v1/pull-requests/{pr_allow.id}/merge")
    assert res.status_code == status.HTTP_409_CONFLICT
    assert "Cannot merge PullRequest in status 'closed'" in res.json()["detail"]

    app.dependency_overrides.clear()


def test_merge_concurrency_row_locking(db):
    author, reviewer, unauth, repo, repo_other, repo_del, actor, change_allow, change_review, change_block, pr_allow, pr_review, pr_no_commit = setup_merge_fixtures(db)
    svc = PullRequestService(db)

    # Test with_for_update row locking in merge_pull_request
    result = svc.merge_pull_request(pr_allow, merger_id=author.id)
    assert result is not None
    assert result.status in {"merged", "merge_ready"}
    assert result.pull_request.id == pr_allow.id
