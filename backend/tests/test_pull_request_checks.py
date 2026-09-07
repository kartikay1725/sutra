import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.main import app
from app.models.actor import Actor
from app.models.change import Change
from app.models.ci_job import CIJob
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.providers.base import RepositoryProvider
from app.services.ci_service import CIService


class MockChecksRepositoryProvider:
    """Mock repository provider simulating GitHub Checks API for unit testing."""

    def __init__(self, check_runs: Optional[List[Dict[str, Any]]] = None):
        self._check_runs = check_runs or []

    def get_metadata(self, owner: str, name: str):
        raise NotImplementedError()

    def get_default_branch(self, owner: str, name: str) -> str:
        return "main"

    def get_branch_head(self, owner: str, name: str, branch: str) -> str:
        return "head_sha_12345"

    def list_branches(self, owner: str, name: str):
        return []

    def get_commit(self, owner: str, name: str, sha: str):
        raise NotImplementedError()

    def get_diff_stats(self, owner: str, name: str, base: str, head: str):
        raise NotImplementedError()

    def get_pull_request(self, owner: str, name: str, number: int):
        raise NotImplementedError()

    def create_pull_request(self, owner: str, name: str, title: str, head: str, base: str, body: Optional[str] = None, is_draft: bool = False):
        raise NotImplementedError()

    def list_check_runs(self, owner: str, name: str, ref: str) -> List[Dict[str, Any]]:
        return [cr for cr in self._check_runs if cr.get("head_sha") == ref]

    def create_check_run(
        self,
        owner: str,
        name: str,
        check_name: str,
        head_sha: str,
        status: str = "completed",
        conclusion: Optional[str] = "success",
        title: Optional[str] = None,
        summary: Optional[str] = None,
        details_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        cr = {
            "id": int(time.time() * 1000) % 1000000,
            "name": check_name,
            "head_sha": head_sha,
            "status": status,
            "conclusion": conclusion if status == "completed" else None,
            "html_url": details_url or f"https://github.com/{owner}/{name}/runs/mock",
            "details_url": details_url,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat() if status == "completed" else None,
            "app": {"name": "GitHub Actions"},
        }
        self._check_runs.append(cr)
        return cr


@pytest.fixture
def checks_test_setup(db: Session):
    user = User(
        id=str(uuid4()),
        username=f"checks_user_{uuid4().hex[:8]}",
        email=f"checks_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
    )
    db.add(user)
    db.flush()

    actor = Actor(
        id=user.id,
        owner_id=user.id,
        type="human",
        name=user.username,
        capabilities=json.dumps(["repository.read", "repository.write", "change.create"]),
    )
    db.add(actor)
    db.flush()

    repo = Repository(
        id=str(uuid4()),
        owner_id=user.id,
        name=f"checks-repo-{uuid4().hex[:6]}",
        slug=f"checks-repo-{uuid4().hex[:6]}",
        visibility="public",
        storage_key=f"checks/{uuid4().hex}",
        provider_type="github",
        provider_owner="kartikay1725",
        default_branch="main",
        settings={},
    )
    db.add(repo)
    db.flush()

    head_commit = f"commit_{uuid4().hex[:12]}"
    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=user.id,
        intent="Add automated checks verification",
        status="recorded",
        resulting_commit=head_commit,
        base_commit="base_commit_000",
        metadata_json=json.dumps({"branch": "feature/ci-checks"}),
    )
    db.add(change)
    db.flush()

    pr = PullRequest(
        id=str(uuid4()),
        repository_id=repo.id,
        author_id=user.id,
        source_change_id=change.id,
        title="Feature: Automated Checks",
        target_branch="main",
        source_commit=head_commit,
        status="open",
    )
    db.add(pr)
    db.flush()

    task = Task(
        id=str(uuid4()),
        repository_id=repo.id,
        created_by=user.id,
        title="Verify Pull Request CI",
        status=Task.STATUS_IN_PROGRESS,
        resulting_change_id=change.id,
        resulting_pull_request_id=pr.id,
    )
    db.add(task)
    db.commit()

    return {
        "user": user,
        "repo": repo,
        "change": change,
        "pr": pr,
        "task": task,
        "head_commit": head_commit,
    }


def test_pr_checks_empty_initial_state(db: Session, checks_test_setup):
    pr = checks_test_setup["pr"]
    user = checks_test_setup["user"]

    svc = CIService(db, provider=MockChecksRepositoryProvider([]))
    data = svc.get_pr_checks(pr.id, user.id)

    assert data["pull_request_id"] == pr.id
    assert data["head_sha"] == checks_test_setup["head_commit"]
    assert data["overall_status"] == "none"
    assert data["governance_verdict"] == "NO CHECKS REPORTED"
    assert data["ready_for_governance"] is False
    assert data["summary"]["total"] == 0
    assert len(data["checks"]) == 0


def test_pr_checks_all_passing_ready_for_governance(db: Session, checks_test_setup):
    pr = checks_test_setup["pr"]
    user = checks_test_setup["user"]
    head_sha = checks_test_setup["head_commit"]

    mock_runs = [
        {
            "id": 101,
            "name": "lint",
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://github.com/runs/101",
            "app": {"name": "GitHub Actions"},
        },
        {
            "id": 102,
            "name": "unit-tests",
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://github.com/runs/102",
            "app": {"name": "GitHub Actions"},
        },
    ]

    svc = CIService(db, provider=MockChecksRepositoryProvider(mock_runs))
    data = svc.get_pr_checks(pr.id, user.id)

    assert data["overall_status"] == "passed"
    assert data["governance_verdict"] == "READY FOR GOVERNANCE"
    assert data["ready_for_governance"] is True
    assert data["summary"]["total"] == 2
    assert data["summary"]["passed"] == 2
    assert data["summary"]["failed"] == 0

    # Verify SUTRA persisted the check runs in CIJob table
    jobs = db.query(CIJob).filter(CIJob.pull_request_id == pr.id).all()
    assert len(jobs) == 2
    assert all(j.status == CIJob.STATUS_PASSED for j in jobs)


def test_pr_checks_failing_blocks_governance(db: Session, checks_test_setup):
    pr = checks_test_setup["pr"]
    user = checks_test_setup["user"]
    head_sha = checks_test_setup["head_commit"]

    mock_runs = [
        {
            "id": 201,
            "name": "lint",
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://github.com/runs/201",
            "app": {"name": "GitHub Actions"},
        },
        {
            "id": 202,
            "name": "integration-tests",
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": "failure",
            "html_url": "https://github.com/runs/202",
            "app": {"name": "GitHub Actions"},
        },
    ]

    svc = CIService(db, provider=MockChecksRepositoryProvider(mock_runs))
    data = svc.get_pr_checks(pr.id, user.id)

    assert data["overall_status"] == "failed"
    assert data["governance_verdict"] == "BLOCKED BY CI"
    assert data["ready_for_governance"] is False
    assert data["summary"]["total"] == 2
    assert data["summary"]["passed"] == 1
    assert data["summary"]["failed"] == 1


def test_pr_checks_running_state_in_progress(db: Session, checks_test_setup):
    pr = checks_test_setup["pr"]
    user = checks_test_setup["user"]
    head_sha = checks_test_setup["head_commit"]

    mock_runs = [
        {
            "id": 301,
            "name": "build",
            "head_sha": head_sha,
            "status": "in_progress",
            "conclusion": None,
            "html_url": "https://github.com/runs/301",
            "app": {"name": "GitHub Actions"},
        }
    ]

    svc = CIService(db, provider=MockChecksRepositoryProvider(mock_runs))
    data = svc.get_pr_checks(pr.id, user.id)

    assert data["overall_status"] == "running"
    assert data["governance_verdict"] == "CHECKS IN PROGRESS"
    assert data["ready_for_governance"] is False
    assert data["summary"]["running"] == 1


def test_pr_checks_head_commit_isolation(db: Session, checks_test_setup):
    pr = checks_test_setup["pr"]
    user = checks_test_setup["user"]
    head_sha = checks_test_setup["head_commit"]
    old_commit_sha = f"old_commit_{uuid4().hex[:12]}"

    # Add a check run belonging to an older commit
    old_job = CIJob(
        id=str(uuid4()),
        pull_request_id=pr.id,
        repository_id=checks_test_setup["repo"].id,
        change_id=checks_test_setup["change"].id,
        commit_sha=old_commit_sha,
        target_branch="main",
        status=CIJob.STATUS_FAILED,
        trigger="unit-tests-old",
        runner_type="github_actions",
    )
    db.add(old_job)
    db.commit()

    # Head commit has passing checks on mock substrate
    mock_runs = [
        {
            "id": 401,
            "name": "test-new",
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://github.com/runs/401",
            "app": {"name": "GitHub Actions"},
        }
    ]

    svc = CIService(db, provider=MockChecksRepositoryProvider(mock_runs))
    data = svc.get_pr_checks(pr.id, user.id)

    # Effective check state must only reflect current head commit!
    assert data["overall_status"] == "passed"
    assert data["governance_verdict"] == "READY FOR GOVERNANCE"
    assert data["summary"]["total"] == 1
    assert data["summary"]["passed"] == 1
    assert data["summary"]["failed"] == 0
