import json
import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db.session import SessionLocal
from app.core.security import hash_password, create_access_token
from app.models.user import User
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.repository import Repository
from app.models.task import Task
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.ci_job import CIJob
from app.models.change_event import ChangeEvent
from app.services.pull_request_service import PullRequestService
from app.services.governance_service import GovernanceVerdict


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_setup(db_session):
    user = User(
        id=str(uuid4()),
        email=f"gov_merge_{uuid4().hex[:8]}@example.com",
        username=f"user_merge_{uuid4().hex[:8]}",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)

    reviewer = User(
        id=str(uuid4()),
        email=f"gov_rev_{uuid4().hex[:8]}@example.com",
        username=f"rev_merge_{uuid4().hex[:8]}",
        password_hash=hash_password("password123"),
    )
    db_session.add(reviewer)
    db_session.flush()

    user_actor = Actor(
        id=user.id,
        owner_id=user.id,
        type="human",
        name=user.username,
        capabilities=json.dumps(["repository.read", "repository.write", "change.create", "change.review", "change.approve"]),
    )
    db_session.add(user_actor)

    reviewer_actor = Actor(
        id=reviewer.id,
        owner_id=reviewer.id,
        type="human",
        name=reviewer.username,
        capabilities=json.dumps(["repository.read", "repository.write", "change.create", "change.review", "change.approve"]),
    )
    db_session.add(reviewer_actor)

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="AtlasMergeAgent",
        description="Autonomous Coding Agent",
        token_prefix="agt_merge_",
        token_hash=hash_password("agent_token_secret"),
        is_active=True,
        status="active",
    )
    db_session.add(agent)
    db_session.flush()

    agent_actor = Actor(
        id=agent.id,
        owner_id=user.id,
        type="agent",
        name=agent.name,
        capabilities=json.dumps(["repository.read", "repository.write", "change.create", "change.commit"]),
    )
    db_session.add(agent_actor)

    repo = Repository(
        id=str(uuid4()),
        owner_id=user.id,
        name="test-merge-repo",
        slug=f"{user.username}/test-merge-repo",
        visibility="public",
        storage_key=f"mock/storage/{uuid4().hex}",
        provider_type="local",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.flush()

    commit_a = "1111111111111111111111111111111111111111"

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=agent.id,
        intent="Test governed merge flow",
        base_commit="0000000000000000000000000000000000000000",
        resulting_commit=commit_a,
        status="recorded",
        risk_level="low",
        metadata_json=json.dumps({
            "task_id": "none",
            "agent_id": agent.id,
            "agent_name": agent.name,
        }),
    )
    db_session.add(change)
    db_session.flush()

    task = Task(
        id=str(uuid4()),
        repository_id=repo.id,
        created_by=user.id,
        assigned_agent_id=agent.id,
        title="Implement Governed Feature",
        status=Task.STATUS_IN_PROGRESS,
        resulting_change_id=change.id,
    )
    db_session.add(task)
    db_session.flush()

    pr = PullRequest(
        id=str(uuid4()),
        repository_id=repo.id,
        author_id=agent.id,
        source_change_id=change.id,
        title="Governed Merge Test PR",
        target_branch="main",
        source_commit=commit_a,
        status=PullRequest.STATUS_OPEN,
    )
    db_session.add(pr)
    task.resulting_pull_request_id = pr.id
    db_session.flush()

    db_session.commit()

    return {
        "user": user,
        "reviewer": reviewer,
        "agent": agent,
        "repo": repo,
        "task": task,
        "change": change,
        "pr": pr,
        "commit_a": commit_a,
    }


def test_agent_cannot_invoke_merge(db_session, test_setup):
    """INVARIANT: Agents must be strictly denied from executing merge."""
    svc = PullRequestService(db_session)
    agent = test_setup["agent"]
    pr = test_setup["pr"]

    with pytest.raises(PermissionError) as exc:
        svc.merge_pull_request(pr.id, merger_id=agent.id)

    assert "Agents are strictly prohibited from merging pull requests" in str(exc.value)


def test_unauthorized_human_cannot_merge(db_session, test_setup):
    """Users without repository write/merge access must be rejected."""
    unauth_user = User(
        id=str(uuid4()),
        email=f"unauth_{uuid4().hex[:8]}@example.com",
        username=f"unauth_{uuid4().hex[:8]}",
        password_hash=hash_password("password123"),
    )
    db_session.add(unauth_user)
    db_session.commit()

    repo = test_setup["repo"]
    repo.visibility = "private"
    db_session.commit()

    svc = PullRequestService(db_session)
    pr = test_setup["pr"]

    with pytest.raises(PermissionError):
        svc.merge_pull_request(pr.id, merger_id=unauth_user.id)


def test_merge_rejected_when_pr_not_approved(db_session, test_setup):
    """A pull request that lacks human approval must be rejected by governance."""
    svc = PullRequestService(db_session)
    pr = test_setup["pr"]
    user = test_setup["user"]
    change = test_setup["change"]

    # CI passed
    ci = CIJob(
        id=str(uuid4()),
        pull_request_id=pr.id,
        repository_id=pr.repository_id,
        change_id=change.id,
        commit_sha=pr.source_commit,
        target_branch="main",
        status=CIJob.STATUS_PASSED,
        trigger="pytest",
    )
    db_session.add(ci)
    db_session.commit()

    with pytest.raises(ValueError) as exc:
        svc.merge_pull_request(pr.id, merger_id=user.id)

    assert "Merge rejected by SUTRA governance" in str(exc.value)


def test_merge_rejected_when_ci_failing(db_session, test_setup):
    """A pull request with failing CI must be rejected even if approved."""
    svc = PullRequestService(db_session)
    pr = test_setup["pr"]
    user = test_setup["user"]
    reviewer = test_setup["reviewer"]
    change = test_setup["change"]

    # Approved by human reviewer
    review = ChangeReview(
        id=str(uuid4()),
        change_id=change.id,
        requested_by=user.id,
        reviewer_id=reviewer.id,
        status="approved",
    )
    db_session.add(review)
    pr.status = PullRequest.STATUS_APPROVED

    # Storing approved HEAD
    change.metadata_json = json.dumps({
        "approved_head_sha": pr.source_commit,
        "reviewed_head_shas": {review.id: pr.source_commit},
    })

    # But CI failed
    ci = CIJob(
        id=str(uuid4()),
        pull_request_id=pr.id,
        repository_id=pr.repository_id,
        change_id=change.id,
        commit_sha=pr.source_commit,
        target_branch="main",
        status=CIJob.STATUS_FAILED,
        trigger="pytest",
    )
    db_session.add(ci)
    db_session.commit()

    with pytest.raises(ValueError) as exc:
        svc.merge_pull_request(pr.id, merger_id=user.id)

    assert "Merge rejected by SUTRA governance" in str(exc.value)


def test_merge_rejected_when_head_changed_after_approval(db_session, test_setup):
    """If PR HEAD changes after human approval, merge authorization is invalidated."""
    svc = PullRequestService(db_session)
    pr = test_setup["pr"]
    user = test_setup["user"]
    reviewer = test_setup["reviewer"]
    change = test_setup["change"]

    old_commit = test_setup["commit_a"]
    new_commit = "2222222222222222222222222222222222222222"

    review = ChangeReview(
        id=str(uuid4()),
        change_id=change.id,
        requested_by=user.id,
        reviewer_id=reviewer.id,
        status="approved",
    )
    db_session.add(review)

    # Approved against old commit
    change.metadata_json = json.dumps({
        "approved_head_sha": old_commit,
        "reviewed_head_shas": {review.id: old_commit},
    })

    # Now PR HEAD changes to new commit
    pr.source_commit = new_commit
    change.resulting_commit = new_commit
    pr.status = PullRequest.STATUS_APPROVED
    db_session.commit()

    with pytest.raises(ValueError) as exc:
        svc.merge_pull_request(pr.id, merger_id=user.id)

    assert "Merge authorization invalidated: PR HEAD changed since governance evaluation." in str(exc.value) or "Merge rejected by SUTRA governance" in str(exc.value)


def test_merge_succeeds_for_governed_pr(db_session, test_setup):
    """When all governance preconditions pass, merge succeeds and updates Task/Change state."""
    svc = PullRequestService(db_session)
    pr = test_setup["pr"]
    user = test_setup["user"]
    reviewer = test_setup["reviewer"]
    change = test_setup["change"]
    task = test_setup["task"]
    head_sha = test_setup["commit_a"]

    # CI passed
    ci = CIJob(
        id=str(uuid4()),
        pull_request_id=pr.id,
        repository_id=pr.repository_id,
        change_id=change.id,
        commit_sha=head_sha,
        target_branch="main",
        status=CIJob.STATUS_PASSED,
        trigger="pytest",
    )
    db_session.add(ci)

    # Human approval satisfied
    review = ChangeReview(
        id=str(uuid4()),
        change_id=change.id,
        requested_by=user.id,
        reviewer_id=reviewer.id,
        status="approved",
    )
    db_session.add(review)

    change.metadata_json = json.dumps({
        "approved_head_sha": head_sha,
        "reviewed_head_shas": {review.id: head_sha},
    })
    pr.status = PullRequest.STATUS_APPROVED
    db_session.commit()

    # Mock server-side git merge transport execution for local repository
    from unittest.mock import patch
    from app.services.git_merge_service import GitMergeResult

    mock_res = GitMergeResult(
        success=True,
        resulting_commit="9999999999999999999999999999999999999999",
        target_branch="main",
        previous_target_commit="0000000000000000000000000000000000000000",
        is_fast_forward=False,
    )

    with patch("app.services.git_merge_service.GitMergeService.execute_server_side_merge", return_value=mock_res):
        res = svc.merge_pull_request(pr.id, merger_id=user.id)

    assert res is not None
    assert res.status == "merged"
    assert res.merge_commit_sha == "9999999999999999999999999999999999999999"

    # Verify PR state
    db_session.refresh(pr)
    assert pr.status == PullRequest.STATUS_MERGED
    assert pr.target_commit == "9999999999999999999999999999999999999999"
    assert pr.merged_at is not None

    # Verify Change state
    db_session.refresh(change)
    assert change.status == "recorded"
    c_meta = json.loads(change.metadata_json)
    assert c_meta["merged"] is True
    assert c_meta["merge_commit_sha"] == "9999999999999999999999999999999999999999"

    # Verify Task completed
    db_session.refresh(task)
    assert task.status == Task.STATUS_COMPLETED
    assert task.completed_at is not None

    # Verify audit event
    events = db_session.scalars(
        select(ChangeEvent).where(
            ChangeEvent.change_id == change.id,
            ChangeEvent.event_type == "pull_request.merged",
        )
    ).all()
    assert len(events) >= 1
    last_event = events[-1]
    meta = json.loads(last_event.metadata_json)
    assert meta["actor_id"] == user.id
    assert meta["merge_sha"] == "9999999999999999999999999999999999999999"
    assert "token" not in last_event.metadata_json
    assert "secret" not in last_event.metadata_json


def test_merge_idempotency(db_session, test_setup):
    """Calling merge on already merged PR returns merged state without re-executing."""
    svc = PullRequestService(db_session)
    pr = test_setup["pr"]
    user = test_setup["user"]

    pr.status = PullRequest.STATUS_MERGED
    pr.target_commit = "9999999999999999999999999999999999999999"
    pr.merged_at = datetime.now(timezone.utc)
    db_session.commit()

    res = svc.merge_pull_request(pr.id, merger_id=user.id)
    assert res is not None
    assert res.status == "merged"
    assert res.detail == "PullRequest is already merged"
    assert res.merge_commit_sha == "9999999999999999999999999999999999999999"
