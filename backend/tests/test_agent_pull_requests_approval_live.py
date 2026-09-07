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
from app.models.pull_request import PullRequest
from app.models.ci_job import CIJob
from app.services.governance_service import GovernanceService, GovernanceVerdict
from app.services.pull_request_service import PullRequestService


GITHUB_OWNER = "kartikay1725"
GITHUB_REPOSITORY = "dam-project"


def test_live_agent_pull_request_approval_e2e():
    """
    Live Agent Pull Request -> Human Approval Lifecycle E2E against real GitHub substrate:

        Real GitHub repository (kartikay1725/dam-project)
              ↓
        Real SUTRA repository mapping
              ↓
        Registered Agent + Actor + Governed AgentSession
              ↓
        Claimed Task -> Recorded SUTRA Change (with real substrate commit)
              ↓
        POST /v1/agent/tasks/{task_id}/pull-requests -> Real GitHub PR
              ↓
        CASE 1: Governance not ready (failing CI check) -> Human approval rejected
              ↓
        CASE 2: Governance ready (passing CI check) -> Legitimate human approval succeeds:
                - PR transitions to approved
                - Governance verdict becomes READY_FOR_MERGE
                - change_event recorded with sanitized metadata
              ↓
        CASE 3: Agent attempts approval -> Strictly rejected
              ↓
        CASE 4: PR author attempts self-approval -> Strictly rejected
              ↓
        CASE 5: Duplicate human approval -> Handled cleanly / idempotently
              ↓
        CASE 6: PR HEAD changes after approval -> Previous approval invalidated (NEEDS_REVIEW)
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
    change_id = None
    test_branch = f"agent-appr-test-{uuid4().hex[:8]}"
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

        # Create real remote branch on GitHub for this test
        provider.create_branch(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            branch=test_branch,
            commit_sha=master_branch.commit_sha,
        )
        print(f"\nCreated real GitHub test branch: {test_branch} from {master_branch.commit_sha[:8]}")

        # Create real commit on GitHub on test_branch
        test_file_path = f"docs/appr-tests/{test_branch}.md"
        commit_res = provider.create_or_update_file(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            path=test_file_path,
            content=f"# Human Approval Live Verification\nGenerated: {datetime.now(timezone.utc).isoformat()}\n".encode("utf-8"),
            message=f"feat(approval): test human approval lifecycle stage [{test_branch}]",
            branch=test_branch,
        )
        test_commit_sha = commit_res["commit"]["sha"]
        assert test_commit_sha
        print(f"Committed real file to GitHub: {test_file_path} (HEAD: {test_commit_sha[:8]})")

        # =========================================================
        # 2. Setup SUTRA DB records
        # =========================================================
        now = datetime.now(timezone.utc)
        user = User(
            id=str(uuid4()),
            email=f"sutra_appr_{uuid4().hex[:8]}@example.com",
            username=f"live_appr_user_{uuid4().hex[:8]}",
            password_hash=hash_password("admin_pass"),
        )
        db.add(user)

        reviewer_user = User(
            id=str(uuid4()),
            email=f"sutra_rev_{uuid4().hex[:8]}@example.com",
            username=f"live_rev_user_{uuid4().hex[:8]}",
            password_hash=hash_password("reviewer_pass"),
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
            slug=f"{GITHUB_OWNER}/{GITHUB_REPOSITORY}",
            visibility="public",
            storage_key=f"mock/storage/{uuid4().hex}",
            provider_type="github",
            provider_owner=GITHUB_OWNER,
            default_branch=default_branch,
            settings={},
        )
        db.add(repository)
        db.flush()

        agent_token_raw = f"agt_live_appr_{uuid4().hex[:12]}"
        agent = Agent(
            id=str(uuid4()),
            owner_id=user.id,
            name=f"approval-agent-{uuid4().hex[:6]}",
            description="Live Human Approval Test Agent",
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
            title=f"Approval Task {test_branch}",
            description="Autonomous feature development with Human Approval verification.",
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
        # 3. Create Change, Record Commit, and Create PR via Agent API
        # =========================================================
        client = TestClient(app)
        agent_auth_headers = {
            "Authorization": f"Bearer {session_token}",
        }

        ch_res = client.post(
            f"/v1/agent/tasks/{task.id}/changes",
            headers=agent_auth_headers,
            json={
                "intent": f"Automated approval delivery for {test_branch}",
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

        pr_title = f"feat(agent-approval): automated human approval verification ({test_branch})"
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

        user_token = create_access_token(user.id)
        reviewer_token = create_access_token(reviewer_user.id)
        user_headers = {"Authorization": f"Bearer {user_token}"}
        reviewer_headers = {"Authorization": f"Bearer {reviewer_token}"}

        # Ensure review request exists
        pr_svc = PullRequestService(db, provider=provider)
        pr_obj = db.scalar(select(PullRequest).where(PullRequest.id == sutra_pr_id))
        existing_rev = db.scalar(
            select(ChangeReview).where(
                ChangeReview.change_id == change_id,
                ChangeReview.status == "pending",
            )
        )
        if not existing_rev:
            pr_svc.create_pull_request_review_request(pr_obj, requester_id=user.id)
            db.commit()

        # =========================================================
        # CASE 1: Governance Not Ready (Failing CI) -> Human Approval Rejected
        # =========================================================
        print("\n--- CASE 1: Governance Not Ready (Failing CI) -> Human Approval Rejected ---")
        ci_check = provider.create_check_run(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            check_name="automated-test-suite",
            head_sha=test_commit_sha,
            status="completed",
            conclusion="failure",
        )
        print(f"Created failing GitHub check run: {ci_check.get('name')}")

        appr_case1 = client.post(
            f"/v1/pull-requests/{sutra_pr_id}/approve",
            headers=reviewer_headers,
            json={"reason": "Should be rejected due to failing CI"},
        )
        print(f"CASE 1 Approval Response Code: {appr_case1.status_code}")
        assert appr_case1.status_code in {400, 409}, f"Expected rejection but got: {appr_case1.text}"
        assert "governance evaluation is blocked" in appr_case1.text.lower() or "ci" in appr_case1.text.lower()

        # =========================================================
        # CASE 2: Governance Ready (Passing CI) -> Legitimate Human Approval Succeeds
        # =========================================================
        print("\n--- CASE 2: Governance Ready (Passing CI) -> Legitimate Human Approval Succeeds ---")
        provider.update_check_run(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            check_run_id=ci_check["id"],
            status="completed",
            conclusion="success",
        )
        print("Updated GitHub check run to success.")

        appr_case2 = client.post(
            f"/v1/pull-requests/{sutra_pr_id}/approve",
            headers=reviewer_headers,
            json={"reason": "Approved by legitimate human reviewer - all CI checks passed"},
        )
        assert appr_case2.status_code == 200, f"Approval failed: {appr_case2.text}"
        data2 = appr_case2.json()

        print(f"CASE 2 Approval Status: {data2['status']} (governance_verdict: {data2.get('governance_verdict')})")
        assert data2["status"] == "approved"
        assert data2["approved"] is True
        assert data2["reviewer"] is not None
        assert data2["reviewer"]["id"] == reviewer_user.id
        assert data2["eligible_for_merge"] is True
        assert data2["governance_verdict"] == GovernanceVerdict.READY_FOR_MERGE

        # Verify audit event in ChangeEvent table
        audit_event = db.scalar(
            select(ChangeEvent)
            .where(
                ChangeEvent.change_id == change_id,
                ChangeEvent.event_type == "pull_request.approved",
            )
            .order_by(ChangeEvent.created_at.desc())
        )
        assert audit_event is not None
        assert audit_event.actor_id == reviewer_user.id
        meta2 = json.loads(audit_event.metadata_json or "{}")
        assert meta2.get("head_sha") == test_commit_sha
        assert meta2.get("pull_request_id") == sutra_pr_id
        assert "token" not in meta2
        print("Verified audit event logged to ChangeEvent with sanitized metadata.")

        # =========================================================
        # CASE 3: Agent Attempts Approval -> Strictly Rejected
        # =========================================================
        print("\n--- CASE 3: Agent Attempts Approval -> Strictly Rejected ---")
        pr_obj = db.scalar(select(PullRequest).where(PullRequest.id == sutra_pr_id))
        try:
            pr_svc.approve_pull_request(pr_obj, approver_id=agent.id)
            assert False, "Agent approval attempt should have raised ValueError"
        except ValueError as exc:
            print(f"Agent approval rejected successfully: {exc}")
            assert "Agents cannot approve pull requests" in str(exc) or "Self-review approval is strictly prohibited" in str(exc)

        # =========================================================
        # CASE 4: PR Author Attempts Self-Approval -> Strictly Rejected
        # =========================================================
        print("\n--- CASE 4: Author Attempts Self-Approval -> Strictly Rejected ---")
        pr_obj.author_id = user.id
        db.commit()
        try:
            pr_svc.approve_pull_request(pr_obj, approver_id=user.id)
            assert False, "Author self-approval attempt should have raised ValueError"
        except ValueError as exc:
            print(f"Author self-approval rejected successfully: {exc}")
            assert "Self-review approval is strictly prohibited" in str(exc)

        # Restore author
        pr_obj.author_id = agent.id
        db.commit()

        # =========================================================
        # CASE 5: Duplicate Human Approval -> Handled Idempotently
        # =========================================================
        print("\n--- CASE 5: Duplicate Human Approval -> Handled Idempotently ---")
        appr_case5 = client.post(
            f"/v1/pull-requests/{sutra_pr_id}/approve",
            headers=reviewer_headers,
            json={"reason": "Duplicate approval by same reviewer"},
        )
        assert appr_case5.status_code == 200
        data5 = appr_case5.json()
        assert data5["status"] == "approved"
        assert data5["approved"] is True

        reviews = db.scalars(
            select(ChangeReview).where(
                ChangeReview.change_id == change_id,
                ChangeReview.status == "approved",
            )
        ).all()
        unique_reviewers = {r.reviewer_id for r in reviews}
        assert len(unique_reviewers) == 1
        print(f"Duplicate approval handled cleanly: {len(unique_reviewers)} unique approver recorded.")

        # =========================================================
        # CASE 6: PR HEAD Changes -> Approval Invalidated for New HEAD
        # =========================================================
        print("\n--- CASE 6: PR HEAD Changes -> Approval Invalidated for New HEAD ---")
        # Push a new commit on the real GitHub branch
        new_commit_res = provider.create_or_update_file(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            path=f"docs/appr-tests/{test_branch}_update.md",
            content=f"# New commit on branch\n{datetime.now(timezone.utc).isoformat()}\n".encode("utf-8"),
            message=f"feat(approval): update PR HEAD commit [{test_branch}]",
            branch=test_branch,
        )
        new_head_sha = new_commit_res["commit"]["sha"]
        assert new_head_sha != test_commit_sha
        print(f"Pushed new commit to GitHub branch: {new_head_sha[:8]}")

        # Update PR and Change with new HEAD commit
        pr_obj.source_commit = new_head_sha
        change_record = db.scalar(select(Change).where(Change.id == change_id))
        change_record.resulting_commit = new_head_sha
        db.commit()

        # Add passing CI for the new commit
        provider.create_check_run(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            check_name="automated-test-suite",
            head_sha=new_head_sha,
            status="completed",
            conclusion="success",
        )

        # Re-evaluate governance via API
        gov_resp_case6 = client.get(f"/v1/pull-requests/{sutra_pr_id}/governance", headers=user_headers)
        assert gov_resp_case6.status_code == 200
        data6 = gov_resp_case6.json()

        print(f"CASE 6 Governance Verdict on new HEAD: {data6['verdict']}")
        assert data6["verdict"] == GovernanceVerdict.NEEDS_REVIEW
        assert data6["review"]["satisfied"] is False
        assert any("earlier commit" in w or "requires fresh review" in w for w in data6["warnings"])
        print(f"Approval invalidation verified: warnings = {data6['warnings']}")

        print("\nALL 6 LIVE HUMAN APPROVAL CASES SUCCESSFULLY VERIFIED AGAINST GITHUB!")

    finally:
        print("\nCleaning up live test resources on GitHub and SUTRA...")

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
            if change_id:
                db.query(ChangeReview).filter(ChangeReview.change_id == change_id).delete()
                db.query(ChangeEvent).filter(ChangeEvent.change_id == change_id).delete()
                db.query(CIJob).filter(CIJob.change_id == change_id).delete()
                db.query(PullRequest).filter(PullRequest.source_change_id == change_id).delete()
                db.query(Change).filter(Change.id == change_id).delete()
            if task:
                db.query(Task).filter(Task.id == task.id).delete()
            if session:
                db.query(AgentSession).filter(AgentSession.id == session.id).delete()
            if actor:
                db.query(Actor).filter(Actor.id == actor.id).delete()
            if agent:
                db.query(Agent).filter(Agent.id == agent.id).delete()
            if repository:
                db.query(Repository).filter(Repository.id == repository.id).delete()
            if user_actor:
                db.query(Actor).filter(Actor.id == user_actor.id).delete()
            if reviewer_actor:
                db.query(Actor).filter(Actor.id == reviewer_actor.id).delete()
            if user:
                db.execute(text("DELETE FROM notifications WHERE user_id = :uid"), {"uid": user.id})
                db.query(User).filter(User.id == user.id).delete()
            if reviewer_user:
                db.execute(text("DELETE FROM notifications WHERE user_id = :uid"), {"uid": reviewer_user.id})
                db.query(User).filter(User.id == reviewer_user.id).delete()
            db.commit()
            print("Cleaned up temporary SUTRA database records.")
        except Exception as e:
            db.rollback()
            print(f"Warning during DB cleanup: {e}")
        finally:
            db.close()


if __name__ == "__main__":
    test_live_agent_pull_request_approval_e2e()
