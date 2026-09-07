import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, create_access_token
from app.main import app
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.branch_protection_rule import BranchProtectionRule
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.change_review import ChangeReview
from app.models.ci_job import CIJob
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.services.governance_service import GovernanceService, GovernanceVerdict
from app.services.pull_request_service import PullRequestService


class MockApprovalRepositoryProvider:
    def __init__(self, check_runs: Optional[List[Dict[str, Any]]] = None):
        self._check_runs = check_runs or []

    def get_default_branch(self, owner: str, name: str) -> str:
        return "main"

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
def approval_test_setup(db: Session):
    user = User(
        id=str(uuid4()),
        username=f"appr_user_{uuid4().hex[:8]}",
        email=f"appr_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
    )
    db.add(user)

    reviewer_user = User(
        id=str(uuid4()),
        username=f"appr_reviewer_{uuid4().hex[:8]}",
        email=f"appr_rev_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
    )
    db.add(reviewer_user)
    db.flush()

    user_actor = Actor(
        id=user.id,
        owner_id=user.id,
        type="human",
        name=user.username,
        capabilities='["repository.read", "repository.write", "change.create", "change.review", "change.approve"]',
    )
    db.add(user_actor)

    reviewer_actor = Actor(
        id=reviewer_user.id,
        owner_id=reviewer_user.id,
        type="human",
        name=reviewer_user.username,
        capabilities='["repository.read", "repository.write", "change.create", "change.review", "change.approve"]',
    )
    db.add(reviewer_actor)

    repo = Repository(
        id=str(uuid4()),
        owner_id=user.id,
        name=f"test-approval-repo-{uuid4().hex[:6]}",
        slug=f"test-approval-repo-{uuid4().hex[:6]}",
        visibility="private",
        storage_key=f"mock/storage/{uuid4().hex}",
        provider_type="github",
        provider_owner="kartikay1725",
        default_branch="main",
        settings={},
    )
    db.add(repo)
    db.flush()

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="test-approval-agent",
        token_prefix="agt_appr_",
        token_hash=hash_password("agent_token_secret"),
        is_active=True,
        status="active",
    )
    db.add(agent)

    actor = Actor(
        id=agent.id,
        owner_id=user.id,
        type="agent",
        name=agent.name,
        capabilities='["repository.read", "repository.write", "change.create", "change.commit", "change.review"]',
    )
    db.add(actor)

    session = AgentSession(
        id=str(uuid4()),
        agent_id=agent.id,
        token_prefix="ses_appr_",
        token_hash=hash_password("session_token_secret"),
        status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(session)

    head_commit = "9999999999999999999999999999999999999999"
    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=agent.id,
        intent="Implement Human Approved Feature",
        status="proposed",
        risk_level="low",
        base_commit="0000000000000000000000000000000000000000",
        resulting_commit=head_commit,
        metadata_json=json.dumps({
            "branch": "feature/approval-test",
            "base_branch": "main",
            "agent_session_id": session.id,
        }),
    )
    db.add(change)
    db.flush()

    pr = PullRequest(
        id=str(uuid4()),
        repository_id=repo.id,
        author_id=agent.id,
        source_change_id=change.id,
        title="Agent PR for Human Approval Test",
        description="Autonomous feature PR delivery.",
        target_branch="main",
        source_commit=head_commit,
        target_commit="0000000000000000000000000000000000000000",
        status=PullRequest.STATUS_OPEN,
    )
    db.add(pr)
    db.flush()

    task = Task(
        id=str(uuid4()),
        repository_id=repo.id,
        created_by=user.id,
        title="Implement Governed Feature",
        status="in_progress",
        assigned_agent_id=agent.id,
        claimed_by_session_id=session.id,
        resulting_change_id=change.id,
        resulting_pull_request_id=pr.id,
    )
    db.add(task)
    db.commit()

    return {
        "user": user,
        "reviewer_user": reviewer_user,
        "repo": repo,
        "agent": agent,
        "actor": actor,
        "session": session,
        "task": task,
        "change": change,
        "pr": pr,
        "head_commit": head_commit,
    }


def test_human_approval_succeeds_on_eligible_pr(db: Session, approval_test_setup):
    """
    CASE 1: When governance preconditions are met, a legitimate human reviewer approval succeeds,
    transitions PR to STATUS_APPROVED, and governance verdict becomes READY_FOR_MERGE.
    """
    setup = approval_test_setup
    provider = MockApprovalRepositoryProvider()
    provider.create_check_run("kartikay1725", setup["repo"].name, "pytest", setup["head_commit"], status="completed", conclusion="success")

    pr_svc = PullRequestService(db, provider=provider)
    pr_svc.create_pull_request_review_request(setup["pr"], requester_id=setup["user"].id)

    approved_pr = pr_svc.approve_pull_request(
        setup["pr"],
        approver_id=setup["reviewer_user"].id,
        reason="Looks great to me!",
    )
    db.commit()

    assert approved_pr.status == PullRequest.STATUS_APPROVED

    gov_svc = GovernanceService(db, provider=provider)
    gov_res = gov_svc.evaluate_pull_request(setup["pr"].id, actor_id=setup["user"].id)

    assert gov_res["verdict"] == GovernanceVerdict.READY_FOR_MERGE
    assert gov_res["ready_for_merge"] is True
    assert gov_res["ready_for_approval"] is True
    assert gov_res["review"]["satisfied"] is True
    assert gov_res["review"]["actual_approvals"] == 1


def test_human_approval_rejected_when_ci_fails(db: Session, approval_test_setup):
    """
    CASE 2: When CI has failed, human approval attempt is rejected with a descriptive error.
    """
    setup = approval_test_setup
    provider = MockApprovalRepositoryProvider()
    provider.create_check_run("kartikay1725", setup["repo"].name, "pytest", setup["head_commit"], status="completed", conclusion="failure")

    pr_svc = PullRequestService(db, provider=provider)
    pr_svc.create_pull_request_review_request(setup["pr"], requester_id=setup["user"].id)

    with pytest.raises(ValueError, match="Cannot approve PullRequest: Governance evaluation is blocked"):
        pr_svc.approve_pull_request(
            setup["pr"],
            approver_id=setup["reviewer_user"].id,
        )


def test_human_approval_rejected_when_ci_pending(db: Session, approval_test_setup):
    """
    CASE 3: When automated CI checks are still in progress, human approval is rejected.
    """
    setup = approval_test_setup
    provider = MockApprovalRepositoryProvider()
    provider.create_check_run("kartikay1725", setup["repo"].name, "pytest", setup["head_commit"], status="in_progress")

    pr_svc = PullRequestService(db, provider=provider)
    pr_svc.create_pull_request_review_request(setup["pr"], requester_id=setup["user"].id)

    with pytest.raises(ValueError, match="Automated CI checks are still running or pending"):
        pr_svc.approve_pull_request(
            setup["pr"],
            approver_id=setup["reviewer_user"].id,
        )


def test_agent_approval_attempt_strictly_rejected(db: Session, approval_test_setup):
    """
    CASE 4: Agent Actor / Agent identity attempts to approve PR -> MUST BE REJECTED.
    """
    setup = approval_test_setup
    pr_svc = PullRequestService(db)
    pr_svc.create_pull_request_review_request(setup["pr"], requester_id=setup["user"].id)

    with pytest.raises(ValueError, match="Agents cannot approve pull requests|Self-review approval is strictly prohibited"):
        pr_svc.approve_pull_request(
            setup["pr"],
            approver_id=setup["agent"].id,
        )


def test_author_self_approval_strictly_rejected(db: Session, approval_test_setup):
    """
    CASE 5: PR author attempts self-approval -> MUST BE REJECTED.
    """
    setup = approval_test_setup
    setup["pr"].author_id = setup["user"].id
    setup["change"].actor_id = setup["user"].id
    db.commit()

    pr_svc = PullRequestService(db)
    pr_svc.create_pull_request_review_request(setup["pr"], requester_id=setup["user"].id)

    with pytest.raises(ValueError, match="Self-review approval is strictly prohibited"):
        pr_svc.approve_pull_request(
            setup["pr"],
            approver_id=setup["user"].id,
        )


def test_duplicate_human_approval_handled_idempotently(db: Session, approval_test_setup):
    """
    CASE 6: Duplicate approval from the same human reviewer is handled idempotently
    and does not duplicate approval counts.
    """
    setup = approval_test_setup
    provider = MockApprovalRepositoryProvider()
    provider.create_check_run("kartikay1725", setup["repo"].name, "pytest", setup["head_commit"], status="completed", conclusion="success")

    pr_svc = PullRequestService(db, provider=provider)
    pr_svc.create_pull_request_review_request(setup["pr"], requester_id=setup["user"].id)

    pr_approved = pr_svc.approve_pull_request(
        setup["pr"],
        approver_id=setup["reviewer_user"].id,
        reason="First approval",
    )
    db.commit()
    assert pr_approved.status == PullRequest.STATUS_APPROVED

    pr_dup = pr_svc.approve_pull_request(
        setup["pr"],
        approver_id=setup["reviewer_user"].id,
        reason="Duplicate approval",
    )
    db.commit()
    assert pr_dup.status == PullRequest.STATUS_APPROVED

    reviews = db.scalars(
        select(ChangeReview).where(
            ChangeReview.change_id == setup["change"].id,
            ChangeReview.status == "approved",
        )
    ).all()
    unique_reviewers = {r.reviewer_id for r in reviews}
    assert len(unique_reviewers) == 1


def test_head_sha_invalidation_when_pr_head_changes(db: Session, approval_test_setup):
    """
    CASE 7: When PR HEAD changes to a new commit SHA after approval,
    previous approval is invalidated and does not authorize the new HEAD.
    """
    setup = approval_test_setup
    provider = MockApprovalRepositoryProvider()
    provider.create_check_run("kartikay1725", setup["repo"].name, "pytest", setup["head_commit"], status="completed", conclusion="success")

    pr_svc = PullRequestService(db, provider=provider)
    pr_svc.create_pull_request_review_request(setup["pr"], requester_id=setup["user"].id)
    pr_svc.approve_pull_request(setup["pr"], approver_id=setup["reviewer_user"].id)
    db.commit()

    gov_svc = GovernanceService(db, provider=provider)
    res_before = gov_svc.evaluate_pull_request(setup["pr"].id)
    assert res_before["verdict"] == GovernanceVerdict.READY_FOR_MERGE
    assert res_before["review"]["satisfied"] is True

    new_head_sha = "8888888888888888888888888888888888888888"
    setup["pr"].source_commit = new_head_sha
    setup["change"].resulting_commit = new_head_sha
    db.commit()

    provider.create_check_run("kartikay1725", setup["repo"].name, "pytest", new_head_sha, status="completed", conclusion="success")
    res_after = gov_svc.evaluate_pull_request(setup["pr"].id)

    assert res_after["verdict"] == GovernanceVerdict.NEEDS_REVIEW
    assert res_after["review"]["satisfied"] is False
    assert any("earlier commit" in w or "Fresh review required" in w or "Fresh approval required" in w for w in res_after["warnings"])


def test_approval_api_endpoint_and_audit(client: TestClient, db: Session, approval_test_setup):
    """
    CASE 8: Verify POST /v1/pull-requests/{id}/approve API endpoint, response contract,
    and audit log emission.
    """
    setup = approval_test_setup
    user_token = create_access_token(setup["reviewer_user"].id)
    headers = {"Authorization": f"Bearer {user_token}"}

    ci_job = CIJob(
        id=str(uuid4()),
        pull_request_id=setup["pr"].id,
        repository_id=setup["repo"].id,
        change_id=setup["change"].id,
        commit_sha=setup["head_commit"],
        target_branch="main",
        status=CIJob.STATUS_PASSED,
        trigger="pytest",
    )
    db.add(ci_job)
    PullRequestService(db).create_pull_request_review_request(setup["pr"], requester_id=setup["user"].id)
    db.commit()

    res = client.post(
        f"/v1/pull-requests/{setup['pr'].id}/approve",
        headers=headers,
        json={"reason": "Approved via API"},
    )
    assert res.status_code == 200, f"Approval API failed: {res.text}"
    data = res.json()

    assert data["status"] == "approved"
    assert data["approved"] is True
    assert data["reviewer"] is not None
    assert data["reviewer"]["id"] == setup["reviewer_user"].id
    assert data["eligible_for_merge"] is True
    assert data["governance_verdict"] == GovernanceVerdict.READY_FOR_MERGE

    audit_entry = db.scalar(
        select(ChangeEvent)
        .where(
            ChangeEvent.event_type == "pull_request.approved",
            ChangeEvent.change_id == setup["change"].id,
        )
        .order_by(ChangeEvent.created_at.desc())
    )
    assert audit_entry is not None
    assert audit_entry.actor_id == setup["reviewer_user"].id
    meta = json.loads(audit_entry.metadata_json or "{}")
    assert meta.get("pull_request_id") == setup["pr"].id
    assert meta.get("head_sha") == setup["head_commit"]
    assert meta.get("actual_approvals") >= 1
    assert "token" not in meta
