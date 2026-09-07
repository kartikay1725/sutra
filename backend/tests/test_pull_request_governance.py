import json
import time
from datetime import datetime, timezone
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


class MockGovernanceRepositoryProvider:
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
def gov_test_setup(db: Session):
    user = User(
        id=str(uuid4()),
        username=f"gov_user_{uuid4().hex[:8]}",
        email=f"gov_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
    )
    db.add(user)

    reviewer_user = User(
        id=str(uuid4()),
        username=f"gov_reviewer_{uuid4().hex[:8]}",
        email=f"gov_rev_{uuid4().hex[:8]}@example.com",
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
        name=f"gov-repo-{uuid4().hex[:6]}",
        slug=f"gov-repo-{uuid4().hex[:6]}",
        storage_key=f"gov-repo-{uuid4().hex[:6]}",
        visibility="public",
        provider_type="github",
        provider_owner="kartikay1725",
    )
    db.add(repo)

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="test_gov_agent",
        token_prefix="agt_gov",
        token_hash="hash_gov",
        is_active=True,
        status="active",
    )
    db.add(agent)
    db.flush()

    actor = Actor(
        id=agent.id,
        owner_id=user.id,
        type="agent",
        name=agent.name,
        capabilities='["repository.read", "repository.write", "change.create", "change.review"]',
    )
    db.add(actor)
    db.flush()

    from datetime import timedelta
    now = datetime.now(timezone.utc)
    session = AgentSession(
        id=str(uuid4()),
        agent_id=agent.id,
        token_hash="hash_sess",
        token_prefix="sess_pfx",
        status="active",
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    db.add(session)
    db.flush()

    head_commit = f"c0ffee{uuid4().hex[:34]}"
    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Add governed feature",
        resulting_commit=head_commit,
        status="recorded",
        risk_level="low",
        metadata_json=json.dumps({
            "branch": "feature/gov",
            "base_branch": "main",
            "agent_session_id": session.id,
        }),
    )
    db.add(change)
    db.flush()

    pr = PullRequest(
        id=str(uuid4()),
        repository_id=repo.id,
        author_id=actor.id,
        source_change_id=change.id,
        title="Add governed feature",
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


def test_governance_verdict_ready_for_approval(db: Session, gov_test_setup):
    """
    CASE 1: All required CI checks pass and reviews are satisfied -> READY_FOR_APPROVAL
    """
    setup = gov_test_setup
    provider = MockGovernanceRepositoryProvider()
    provider.create_check_run("kartikay1725", setup["repo"].name, "pytest", setup["head_commit"], status="completed", conclusion="success")
    provider.create_check_run("kartikay1725", setup["repo"].name, "lint", setup["head_commit"], status="completed", conclusion="success")

    # Add valid human review
    review = ChangeReview(
        id=str(uuid4()),
        change_id=setup["change"].id,
        requested_by=setup["user"].id,
        reviewer_id=setup["reviewer_user"].id,
        status="approved",
        reason="Looks great",
    )
    db.add(review)
    db.commit()

    gov_svc = GovernanceService(db, provider=provider)
    result = gov_svc.evaluate_pull_request(setup["pr"].id, actor_id=setup["user"].id)

    assert result["verdict"] == GovernanceVerdict.READY_FOR_APPROVAL
    assert result["ready_for_approval"] is True
    assert result["checks"]["passed"] == 2
    assert result["checks"]["failed"] == 0
    assert result["provenance"]["verified"] is True
    assert result["policy"]["passed"] is True
    assert result["review"]["satisfied"] is True
    assert len(result["failed"]) == 0


def test_governance_verdict_blocked_when_ci_fails(db: Session, gov_test_setup):
    """
    CASE 2: Required check fails -> Governance = BLOCKED
    """
    setup = gov_test_setup
    provider = MockGovernanceRepositoryProvider()
    provider.create_check_run("kartikay1725", setup["repo"].name, "pytest", setup["head_commit"], status="completed", conclusion="failure")
    provider.create_check_run("kartikay1725", setup["repo"].name, "lint", setup["head_commit"], status="completed", conclusion="success")

    gov_svc = GovernanceService(db, provider=provider)
    result = gov_svc.evaluate_pull_request(setup["pr"].id, actor_id=setup["user"].id)

    assert result["verdict"] == GovernanceVerdict.BLOCKED
    assert result["ready_for_approval"] is False
    assert result["checks"]["failed"] == 1
    assert any("failed" in f.lower() for f in result["failed"])


def test_governance_verdict_ci_pending_when_running(db: Session, gov_test_setup):
    """
    CI checks running -> Governance = CI_PENDING
    """
    setup = gov_test_setup
    provider = MockGovernanceRepositoryProvider()
    provider.create_check_run("kartikay1725", setup["repo"].name, "pytest", setup["head_commit"], status="in_progress")

    gov_svc = GovernanceService(db, provider=provider)
    result = gov_svc.evaluate_pull_request(setup["pr"].id, actor_id=setup["user"].id)

    assert result["verdict"] == GovernanceVerdict.CI_PENDING
    assert result["ready_for_approval"] is False


def test_governance_verdict_needs_review(db: Session, gov_test_setup):
    """
    CASE 3: Checks pass, but required review is missing -> NEEDS_REVIEW
    """
    setup = gov_test_setup
    provider = MockGovernanceRepositoryProvider()
    provider.create_check_run("kartikay1725", setup["repo"].name, "pytest", setup["head_commit"], status="completed", conclusion="success")

    # Ensure branch rule requires 1 approval
    rule = BranchProtectionRule(
        repository_id=setup["repo"].id,
        branch_pattern="main",
        required_approvals=1,
        created_by=setup["user"].id,
        updated_by=setup["user"].id,
    )
    db.add(rule)
    db.commit()

    gov_svc = GovernanceService(db, provider=provider)
    result = gov_svc.evaluate_pull_request(setup["pr"].id, actor_id=setup["user"].id)

    assert result["verdict"] == GovernanceVerdict.NEEDS_REVIEW
    assert result["ready_for_approval"] is False
    assert result["review"]["satisfied"] is False
    assert any("Required reviews not satisfied" in f for f in result["failed"])


def test_governance_agent_self_approval_rejected(db: Session, gov_test_setup):
    """
    CASE 4: Agent attempts self-approval -> MUST BE REJECTED & excluded from governance approval count
    """
    setup = gov_test_setup
    provider = MockGovernanceRepositoryProvider()
    provider.create_check_run("kartikay1725", setup["repo"].name, "pytest", setup["head_commit"], status="completed", conclusion="success")

    # 1. Direct approve_pull_request rejects self approval
    pr_svc = PullRequestService(db)
    with pytest.raises(ValueError, match="Self-review approval is strictly prohibited"):
        pr_svc.approve_pull_request(setup["pr"], approver_id=setup["agent"].id)

    # 2. Even if an author self-approval record existed in ChangeReview, GovernanceService discards it
    setup["pr"].author_id = setup["user"].id
    setup["change"].actor_id = setup["user"].id
    db.commit()

    self_review = ChangeReview(
        id=str(uuid4()),
        change_id=setup["change"].id,
        requested_by=setup["user"].id,
        reviewer_id=setup["user"].id,  # Author self approval!
        status="approved",
        reason="Self approval attempt",
    )
    db.add(self_review)
    db.commit()

    gov_svc = GovernanceService(db, provider=provider)
    result = gov_svc.evaluate_pull_request(setup["pr"].id, actor_id=setup["user"].id)

    assert result["review"]["self_approval_prevented"] is True
    assert result["review"]["actual_approvals"] == 0
    assert result["verdict"] == GovernanceVerdict.NEEDS_REVIEW
    assert any("Self-approval by author/agent is strictly prohibited" in w for w in result["warnings"])


def test_governance_blocked_on_commit_mismatch(db: Session, gov_test_setup):
    """
    Change resulting commit doesn't match PR HEAD commit -> BLOCKED
    """
    setup = gov_test_setup
    setup["pr"].source_commit = "mismatched_head_sha_999"
    db.commit()

    gov_svc = GovernanceService(db)
    result = gov_svc.evaluate_pull_request(setup["pr"].id, actor_id=setup["user"].id)

    assert result["verdict"] == GovernanceVerdict.BLOCKED
    assert any("PR HEAD commit" in f and "does not match" in f for f in result["failed"])


def test_governance_api_endpoints_and_audit(client: TestClient, db: Session, gov_test_setup):
    """
    Verify GET /v1/pull-requests/{id}/governance and POST /v1/pull-requests/{id}/governance/evaluate
    """
    setup = gov_test_setup
    user_token = create_access_token(setup["user"].id)
    headers = {"Authorization": f"Bearer {user_token}"}

    # Add CIJob in SUTRA DB
    ci_job = CIJob(
        id=str(uuid4()),
        pull_request_id=setup["pr"].id,
        repository_id=setup["repo"].id,
        change_id=setup["change"].id,
        commit_sha=setup["head_commit"],
        target_branch="main",
        status=CIJob.STATUS_PASSED,
        trigger="unit-test",
    )
    db.add(ci_job)
    db.commit()

    # GET
    res_get = client.get(f"/v1/pull-requests/{setup['pr'].id}/governance", headers=headers)
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert data_get["pull_request_id"] == setup["pr"].id
    assert "verdict" in data_get
    assert "ready_for_approval" in data_get

    # POST (audit recorded)
    res_post = client.post(f"/v1/pull-requests/{setup['pr'].id}/governance/evaluate", headers=headers)
    assert res_post.status_code == 200
    data_post = res_post.json()
    assert data_post["pull_request_id"] == setup["pr"].id

    # Verify audit event in DB
    audit_event = db.scalar(
        select(ChangeEvent).where(
            ChangeEvent.change_id == setup["change"].id,
            ChangeEvent.event_type == "pull_request.governance_evaluated",
        )
    )
    assert audit_event is not None
    meta = json.loads(audit_event.metadata_json)
    assert meta["pull_request_id"] == setup["pr"].id
    assert "token" not in audit_event.metadata_json.lower()
