"""
Unit tests for GitHub Actions CI delegation, sync, and template service.
"""

from unittest.mock import MagicMock
import pytest
from app.models.ci_job import CIJob
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.services.ci_service import CIService
from app.services.github_actions_template import GitHubActionsTemplateService


def test_github_actions_template_service():
    py_wf = GitHubActionsTemplateService.get_python_ci_workflow(run_tests_cmd="pytest -v")
    assert "name: CI" in py_wf
    assert "uses: actions/checkout@v4" in py_wf
    assert "pytest -v" in py_wf

    node_wf = GitHubActionsTemplateService.get_node_ci_workflow(run_tests_cmd="npm test")
    assert "name: CI" in node_wf
    assert "uses: actions/setup-node@v4" in node_wf
    assert "npm test" in node_wf


def test_sync_github_checks_mapping():
    db = MagicMock()
    repo = Repository(
        id="repo-1",
        name="test-repo",
        provider_type="github",
        provider_owner="octocat",
    )
    pr = PullRequest(
        id="pr-1",
        repository_id="repo-1",
        source_commit="commit-sha-123",
        target_branch="main",
    )

    db.scalar.side_effect = lambda q: pr if "pull_requests" in str(q).lower() else repo

    svc = CIService(db)
    provider_mock = MagicMock()
    provider_mock.list_check_runs.return_value = [
        {
            "id": 101,
            "name": "pytest",
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://github.com/octocat/test-repo/actions/runs/101",
            "started_at": "2026-09-12T18:00:00Z",
            "completed_at": "2026-09-12T18:01:00Z",
        }
    ]
    svc._get_provider = MagicMock(return_value=provider_mock)

    jobs = svc.sync_github_checks("pr-1")
    assert len(jobs) == 1
    assert jobs[0].status == CIJob.STATUS_PASSED
    assert jobs[0].runner_type == "github_actions"
    assert jobs[0].output_log == "https://github.com/octocat/test-repo/actions/runs/101"
