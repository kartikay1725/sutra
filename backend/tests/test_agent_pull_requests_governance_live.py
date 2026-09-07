import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.main import app
from app.db.session import SessionLocal
from app.core.config import settings
from app.core.security import hash_password, create_access_token

from app.models.user import User
from app.models.repository import Repository
from app.models.agent import Agent
from app.models.actor import Actor
from app.models.agent_session import AgentSession
from app.models.task import Task
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.change_review import ChangeReview
from app.models.branch_protection_rule import BranchProtectionRule
from app.models.pull_request import PullRequest
from app.models.ci_job import CIJob
from app.services.governance_service import GovernanceService, GovernanceVerdict
from app.services.pull_request_service import PullRequestService


GITHUB_OWNER = "kartikay1725"
GITHUB_REPOSITORY = "dam-project"


def test_live_agent_pull_request_governance_e2e():
    """
    Live Agent Pull Request -> Governance / Policy Evaluation Lifecycle E2E against real GitHub substrate:

        Real GitHub repository (kartikay1725/dam-project)
              ↓
        Real SUTRA repository mapping
              ↓
        Registered Agent + Actor + Governed AgentSession
              ↓
        Claimed Task -> Recorded SUTRA Change (with real substrate commit)
              ↓
        POST /v1/agent/tasks/{task_id}/pull-requests
              ↓
        Real GitHub Pull Request created with SUTRA Agent Provenance
              ↓
        CASE 1: All required checks pass + review satisfied -> Governance = READY_FOR_APPROVAL
              ↓
        CASE 2: Required check fails -> Governance = BLOCKED
              ↓
        CASE 3: Required review missing -> Governance = NEEDS_REVIEW
              ↓
        CASE 4: Agent attempts self-approval -> MUST BE REJECTED
              ↓
        Safe GitHub cleanup (close PR + delete test branch)
    """
    db = SessionLocal()

    user = None
    reviewer_user = None
    user_actor = None
    reviewer_actor = None
    repository = None
    agent = None
    actor = None
    session = None
    task = None
    change_record = None
    change_id = None
    pr_record = None
    bp_rule = None
    test_branch = f"agent-gov-test-{uuid4().hex[:8]}"
    created_gh_pr_number = None

    try:
        # =========================================================
        # 1. Build REAL GitHub provider
        # =========================================================
        from app.providers.github.auth import GitHubAppAuthService
        from app.providers.github.repository import GitHubRepositoryProvider

        assert settings.github_app_id
        assert settings.github_private_key_pem
        assert settings.github_api_base_url

        auth = GitHubAppAuthService(
            app_id=settings.github_app_id,
            private_key_pem=settings.github_private_key_pem,
            base_url=settings.github_api_base_url,
        )

        provider = GitHubRepositoryProvider(
            auth_service=auth,
            base_url=settings.github_api_base_url,
        )

        # =========================================================
        # 2. Verify real GitHub repo and master branch
        # =========================================================
        branches = provider.list_branches(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
        )
        assert branches, f"GitHub repo {GITHUB_OWNER}/{GITHUB_REPOSITORY} returned no branches"

        default_branch = "master"
        master_branch = next(
            (b for b in branches if getattr(b, "name", None) == default_branch),
            None,
        )
        assert master_branch is not None, f"Expected GitHub branch '{default_branch}' not found"

        print()
        print(f"Verified GitHub repository: {GITHUB_OWNER}/{GITHUB_REPOSITORY}")
        print(f"Verified default branch: {default_branch} (HEAD: {master_branch.commit_sha})")

        # =========================================================
        # 3. Create temporary branch on GitHub and commit a file
        # =========================================================
        provider.create_branch(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            branch=test_branch,
            commit_sha=master_branch.commit_sha,
        )
        print(f"Created temporary GitHub test branch: {test_branch}")

        file_res = provider.create_or_update_file(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            path=f"docs/gov-tests/{test_branch}.md",
            message=f"feat(governance): policy evaluation verification for {test_branch}",
            content=f"# SUTRA Governance Pipeline\nPolicy and review verification for task {test_branch}.\n".encode("utf-8"),
            branch=test_branch,
        )
        test_commit_sha = file_res["commit"]["sha"]
        print(f"Committed file to {test_branch} (SHA: {test_commit_sha})")

        # =========================================================
        # 4. Create temporary SUTRA records
        # =========================================================
        user = User(
            id=str(uuid4()),
            username=f"live_gov_user_{uuid4().hex[:8]}",
            email=f"live_gov_{uuid4().hex[:8]}@example.com",
            password_hash=hash_password("password123"),
        )
        db.add(user)

        reviewer_user = User(
            id=str(uuid4()),
            username=f"live_gov_reviewer_{uuid4().hex[:8]}",
            email=f"live_gov_rev_{uuid4().hex[:8]}@example.com",
            password_hash=hash_password("password123"),
        )
        db.add(reviewer_user)
        db.flush()

        user_actor = Actor(
            id=user.id,
            owner_id=user.id,
            type="human",
            name=user.username,
            capabilities=json.dumps(["repository.read", "repository.write", "change.create", "change.review", "change.approve"]),
        )
        db.add(user_actor)

        reviewer_actor = Actor(
            id=reviewer_user.id,
            owner_id=reviewer_user.id,
            type="human",
            name=reviewer_user.username,
            capabilities=json.dumps(["repository.read", "repository.write", "change.create", "change.review", "change.approve"]),
        )
        db.add(reviewer_actor)

        repository = Repository(
            id=str(uuid4()),
            owner_id=user.id,
            name=GITHUB_REPOSITORY,
            slug=GITHUB_REPOSITORY,
            description="Temporary SUTRA mapping for live Governance E2E",
            visibility="private",
            storage_key=f"github-gov-test/{uuid4().hex}",
            provider_type="github",
            provider_owner=GITHUB_OWNER,
            default_branch=default_branch,
            settings={},
        )
        db.add(repository)

        agent_token_raw = f"agt_live_gov_{uuid4().hex[:12]}"
        agent = Agent(
            id=str(uuid4()),
            owner_id=user.id,
            name=f"governance-agent-{uuid4().hex[:6]}",
            description="Live Governance Test Agent",
            token_prefix=agent_token_raw[:8],
            token_hash=hash_password(agent_token_raw),
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
            capabilities=json.dumps([
                "repository.read",
                "repository.write",
                "change.create",
                "change.commit",
                "change.review",
                "change.conflict.read",
            ]),
        )
        db.add(actor)

        now = datetime.now(timezone.utc)
        session_token = f"sutra_session_{uuid4().hex}_{uuid4().hex}"
        session = AgentSession(
            id=str(uuid4()),
            agent_id=agent.id,
            token_prefix=session_token[:32],
            token_hash=hash_password(session_token),
            status="active",
            created_at=now,
            expires_at=now + timedelta(hours=2),
            last_seen_at=now,
        )
        db.add(session)
        db.flush()

        task = Task(
            id=str(uuid4()),
            repository_id=repository.id,
            created_by=user.id,
            title=f"Governance Task {test_branch}",
            description="Autonomous feature development with GitHub Pull Request Governance verification.",
            status=Task.STATUS_IN_PROGRESS,
            assigned_agent_id=agent.id,
            assigned_user_id=None,
            claimed_by_session_id=session.id,
            lease_expires_at=now + timedelta(hours=1),
            resulting_change_id=None,
            resulting_pull_request_id=None,
        )
        db.add(task)
        db.commit()

        # =========================================================
        # 5. Create Change, Record Commit, and Create PR via Agent API
        # =========================================================
        client = TestClient(app)
        agent_auth_headers = {
            "Authorization": f"Bearer {session_token}",
        }

        ch_res = client.post(
            f"/v1/agent/tasks/{task.id}/changes",
            headers=agent_auth_headers,
            json={
                "intent": f"Automated governance delivery for {test_branch}",
                "branch": test_branch,
                "base_branch": default_branch,
            },
        )
        assert ch_res.status_code == 201, f"Failed to create change: {ch_res.text}"
        change_data = ch_res.json()
        change_id = change_data["id"]
        print(f"Created SUTRA Change: {change_id}")

        commit_res = client.post(
            f"/v1/agent/tasks/{task.id}/commit",
            headers=agent_auth_headers,
            json={
                "resulting_commit": test_commit_sha,
                "commit_sha": test_commit_sha,
            },
        )
        assert commit_res.status_code == 200, f"Failed to record commit: {commit_res.text}"
        print(f"Recorded commit {test_commit_sha} to Change {change_id}")

        pr_title = f"feat(agent-gov): automated governance verification ({test_branch})"
        pr_body = (
            f"Autonomous Agent PR delivery for task `{task.id}`.\n\n"
            f"- **Agent**: `{agent.name}`\n"
            f"- **Session**: `{session.id}`\n"
            f"- **Change**: `{change_id}`\n"
            f"- **Head Commit**: `{test_commit_sha}`\n"
        )
        pr_payload = {
            "title": pr_title,
            "description": pr_body,
            "target_branch": default_branch,
            "is_draft": False,
        }

        pr_create_resp = client.post(
            f"/v1/agent/tasks/{task.id}/pull-requests",
            json=pr_payload,
            headers=agent_auth_headers,
        )
        assert pr_create_resp.status_code == 201, f"Failed to create PR: {pr_create_resp.text}"
        pr_data = pr_create_resp.json()
        sutra_pr_id = pr_data["id"]
        created_gh_pr_number = pr_data.get("github_pr_number")

        print(f"Created SUTRA PR #{sutra_pr_id[:8]} (GitHub PR #{created_gh_pr_number})")

        # =========================================================
        # CASE 1: All Required Checks Pass & Review Satisfied -> READY_FOR_APPROVAL
        # =========================================================
        print("\n--- CASE 1: Passing CI + Satisfied Review -> READY_FOR_APPROVAL ---")
        check_run = provider.create_check_run(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            check_name="pytest-suite",
            head_sha=test_commit_sha,
            status="completed",
            conclusion="success",
        )
        print(f"Created passing check run: {check_run.get('name')}")

        # Human review approval
        human_review = ChangeReview(
            id=str(uuid4()),
            change_id=change_id,
            requested_by=user.id,
            reviewer_id=reviewer_user.id,
            status="approved",
            reason="Verified and approved by human maintainer.",
        )
        db.add(human_review)
        db.commit()

        user_token = create_access_token(user.id)
        user_headers = {"Authorization": f"Bearer {user_token}"}

        gov_resp_case1 = client.get(f"/v1/pull-requests/{sutra_pr_id}/governance", headers=user_headers)
        assert gov_resp_case1.status_code == 200
        data1 = gov_resp_case1.json()

        print(f"CASE 1 Verdict: {data1['verdict']} (ready_for_approval: {data1['ready_for_approval']})")
        assert data1["verdict"] == GovernanceVerdict.READY_FOR_APPROVAL
        assert data1["ready_for_approval"] is True
        assert data1["checks"]["passed"] >= 1
        assert data1["provenance"]["verified"] is True
        assert data1["review"]["satisfied"] is True
        assert len(data1["failed"]) == 0

        # =========================================================
        # CASE 2: Required Check Fails -> BLOCKED
        # =========================================================
        print("\n--- CASE 2: Failing Check -> BLOCKED ---")
        failing_check = provider.create_check_run(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            check_name="security-audit",
            head_sha=test_commit_sha,
            status="completed",
            conclusion="failure",
        )
        print(f"Created failing check run: {failing_check.get('name')}")

        gov_resp_case2 = client.get(f"/v1/pull-requests/{sutra_pr_id}/governance", headers=user_headers)
        assert gov_resp_case2.status_code == 200
        data2 = gov_resp_case2.json()

        print(f"CASE 2 Verdict: {data2['verdict']} (ready_for_approval: {data2['ready_for_approval']})")
        assert data2["verdict"] in (GovernanceVerdict.BLOCKED, GovernanceVerdict.CI_FAILED)
        assert data2["ready_for_approval"] is False
        assert any("failed" in f.lower() for f in data2["failed"])

        # Update the failing check run to success on GitHub so CI is passing for subsequent review tests
        provider.update_check_run(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            check_run_id=failing_check["id"],
            status="completed",
            conclusion="success",
        )

        # =========================================================
        # CASE 3: Required Review Missing -> NEEDS_REVIEW
        # =========================================================
        print("\n--- CASE 3: Required Review Missing -> NEEDS_REVIEW ---")
        # Remove previous approval
        db.query(ChangeReview).filter(ChangeReview.change_id == change_id).delete()
        # Create BranchProtectionRule on target branch requiring 2 approvals
        bp_rule = BranchProtectionRule(
            repository_id=repository.id,
            branch_pattern=default_branch,
            required_approvals=2,
            created_by=user.id,
            updated_by=user.id,
        )
        db.add(bp_rule)
        db.commit()

        gov_resp_case3 = client.get(f"/v1/pull-requests/{sutra_pr_id}/governance", headers=user_headers)
        assert gov_resp_case3.status_code == 200
        data3 = gov_resp_case3.json()

        print(f"CASE 3 Verdict: {data3['verdict']} (ready_for_approval: {data3['ready_for_approval']})")
        assert data3["verdict"] == GovernanceVerdict.NEEDS_REVIEW
        assert data3["ready_for_approval"] is False
        assert data3["review"]["satisfied"] is False
        assert any("Required reviews not satisfied" in f for f in data3["failed"])

        # =========================================================
        # CASE 4: Agent Attempts Self-Approval -> MUST BE REJECTED
        # =========================================================
        print("\n--- CASE 4: Agent Self-Approval Attempt -> MUST BE REJECTED ---")
        pr_obj = db.scalar(select(PullRequest).where(PullRequest.id == sutra_pr_id))
        pr_svc = PullRequestService(db)

        # Attempting self-approval via PullRequestService raises ValueError
        try:
            pr_svc.approve_pull_request(pr_obj, approver_id=agent.id)
            assert False, "Self-approval by agent should have raised ValueError"
        except ValueError as exc:
            print(f"Self-approval rejected successfully with error: {exc}")
            assert "Self-review approval is strictly prohibited" in str(exc)

        # Even if an author tries to approve their own PR, GovernanceService discards it
        pr_record = db.scalar(select(PullRequest).where(PullRequest.id == sutra_pr_id))
        pr_record.author_id = user.id
        db.commit()

        self_review = ChangeReview(
            id=str(uuid4()),
            change_id=change_id,
            requested_by=user.id,
            reviewer_id=user.id,  # Author self-approval attempt
            status="approved",
            reason="Author self approval attempt",
        )
        db.add(self_review)
        db.commit()

        gov_resp_case4 = client.post(f"/v1/pull-requests/{sutra_pr_id}/governance/evaluate", headers=user_headers)
        assert gov_resp_case4.status_code == 200
        data4 = gov_resp_case4.json()

        print(f"CASE 4 Self-Approval Prevented: {data4['review']['self_approval_prevented']}")
        assert data4["review"]["self_approval_prevented"] is True
        assert data4["review"]["satisfied"] is False
        assert any("Self-approval by author/agent is strictly prohibited" in w for w in data4["warnings"])

        print()
        print("ALL 4 GOVERNANCE CASES VERIFIED LIVE AGAINST GITHUB SUBSTRATE!")

    finally:
        print("\nCleaning up live test resources...")

        # Close GitHub PR
        if created_gh_pr_number:
            try:
                provider.close_pull_request(
                    owner=GITHUB_OWNER,
                    name=GITHUB_REPOSITORY,
                    pr_number=created_gh_pr_number,
                )
                print(f"Closed GitHub PR #{created_gh_pr_number}")
            except Exception as e:
                print(f"Warning: Failed to close GitHub PR #{created_gh_pr_number}: {e}")

        # Delete test branch
        try:
            provider.delete_branch(
                owner=GITHUB_OWNER,
                name=GITHUB_REPOSITORY,
                branch=test_branch,
            )
            print(f"Deleted GitHub test branch: {test_branch}")
        except Exception as e:
            print(f"Warning: Failed to delete GitHub test branch: {e}")

        # Clean DB records
        try:
            if bp_rule:
                db.delete(bp_rule)
            if change_id:
                db.query(ChangeReview).filter(ChangeReview.change_id == change_id).delete()
                db.query(ChangeEvent).filter(ChangeEvent.change_id == change_id).delete()
                db.query(CIJob).filter(CIJob.change_id == change_id).delete()
                db.query(PullRequest).filter(PullRequest.source_change_id == change_id).delete()
                db.query(Change).filter(Change.id == change_id).delete()
            if task:
                db.delete(task)
            if session:
                db.delete(session)
            if actor:
                db.delete(actor)
            if agent:
                db.delete(agent)
            if repository:
                db.delete(repository)
            if user_actor:
                db.delete(user_actor)
            if reviewer_actor:
                db.delete(reviewer_actor)
            if user:
                db.execute(text("DELETE FROM notifications WHERE user_id = :uid"), {"uid": user.id})
                db.delete(user)
            if reviewer_user:
                db.execute(text("DELETE FROM notifications WHERE user_id = :uid"), {"uid": reviewer_user.id})
                db.delete(reviewer_user)
            db.commit()
            print("Cleaned up temporary SUTRA database records.")
        except Exception as e:
            db.rollback()
            print(f"Warning during DB cleanup: {e}")
        finally:
            db.close()


if __name__ == "__main__":
    test_live_agent_pull_request_governance_e2e()
