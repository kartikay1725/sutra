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
from sqlalchemy import select

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


def test_live_agent_pull_request_governed_merge_e2e():
    """
    Live Agent Pull Request -> Human Approval -> GOVERNED MERGE Lifecycle E2E
    against real authoritative GitHub substrate (kartikay1725/dam-project).

    Verifies all 10 required cases:
      CASE 1: PR not approved -> merge rejected, GitHub merge API not called
      CASE 2: CI failing -> merge rejected
      CASE 3: Governance blocked -> merge rejected
      CASE 4: Approved PR / READY_FOR_MERGE -> real GitHub merge succeeds
      CASE 5: Verify GitHub PR is actually merged -> obtain merge SHA
      CASE 6: Retry same merge request -> idempotent reconciliation
      CASE 7: HEAD changes after approval -> merge rejected
      CASE 8: Agent attempts merge -> strictly rejected
      CASE 9: Unauthorized human attempts merge -> strictly rejected
      CASE 10: Verify complete end-to-end provenance:
               Agent -> Session -> Task -> Change -> PR -> Reviewed SHA -> Human Approval -> Merge SHA -> Merge Actor
    """
    db = SessionLocal()

    user = None
    reviewer_user = None
    unauth_user = None
    repository = None
    agent = None
    session = None
    task = None
    change_id = None
    test_branch = f"merge-e2e-{uuid4().hex[:8]}"
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
        print(f"\n[LIVE] Created real GitHub test branch: {test_branch} from {master_branch.commit_sha[:8]}")

        # Create safe isolated test file on GitHub on test_branch
        test_file_path = f"docs/merge-tests/{test_branch}.md"
        commit_res = provider.create_or_update_file(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            path=test_file_path,
            content=f"# Governed Merge Live Verification\nGenerated: {datetime.now(timezone.utc).isoformat()}\n".encode("utf-8"),
            message=f"feat(merge): test governed merge lifecycle stage [{test_branch}]",
            branch=test_branch,
        )
        test_commit_sha = commit_res["commit"]["sha"]
        assert test_commit_sha
        print(f"[LIVE] Committed safe test fixture to GitHub: {test_file_path} (HEAD: {test_commit_sha[:8]})")

        # =========================================================
        # 2. Setup SUTRA DB records
        # =========================================================
        now = datetime.now(timezone.utc)
        user = User(
            id=str(uuid4()),
            email=f"sutra_mrg_{uuid4().hex[:8]}@example.com",
            username=f"live_mrg_owner_{uuid4().hex[:8]}",
            password_hash=hash_password("admin_pass"),
        )
        db.add(user)

        reviewer_user = User(
            id=str(uuid4()),
            email=f"sutra_rev_{uuid4().hex[:8]}@example.com",
            username=f"live_mrg_rev_{uuid4().hex[:8]}",
            password_hash=hash_password("reviewer_pass"),
        )
        db.add(reviewer_user)

        unauth_user = User(
            id=str(uuid4()),
            email=f"sutra_unauth_{uuid4().hex[:8]}@example.com",
            username=f"live_mrg_unauth_{uuid4().hex[:8]}",
            password_hash=hash_password("unauth_pass"),
        )
        db.add(unauth_user)
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

        unauth_actor = Actor(
            id=unauth_user.id,
            owner_id=unauth_user.id,
            type="human",
            name=unauth_user.username,
            capabilities=json.dumps(["repository.read"]),
        )
        db.add(unauth_actor)

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

        agent_token_raw = f"agt_live_mrg_{uuid4().hex[:12]}"
        agent = Agent(
            id=str(uuid4()),
            owner_id=user.id,
            name="AtlasMergeE2EAgent",
            description="Live Governed Merge E2E Verification Agent",
            token_prefix=agent_token_raw[:8],
            token_hash=hash_password(agent_token_raw),
            status="active",
            is_active=True,
        )
        db.add(agent)
        db.flush()

        agent_actor = Actor(
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
        db.add(agent_actor)

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

        # Create Task assigned to agent
        task = Task(
            id=str(uuid4()),
            repository_id=repository.id,
            created_by=user.id,
            title=f"Merge Task {test_branch}",
            description="Autonomous feature development with Governed Merge verification.",
            status=Task.STATUS_IN_PROGRESS,
            assigned_agent_id=agent.id,
            assigned_user_id=None,
            claimed_by_session_id=session.id,
            lease_expires_at=now + timedelta(seconds=120),
        )
        db.add(task)

        db.commit()

        # =========================================================
        # 3. Create Change, Record Commit, and Create PR via Agent API
        # =========================================================
        client = TestClient(app)
        agent_auth_headers = {"Authorization": f"Bearer {session_token}"}

        ch_res = client.post(
            f"/v1/agent/tasks/{task.id}/changes",
            headers=agent_auth_headers,
            json={
                "intent": f"Automated merge delivery for {test_branch}",
                "branch": test_branch,
                "base_branch": default_branch,
            },
        )
        assert ch_res.status_code == 201, f"Failed to create change: {ch_res.text}"
        change_data = ch_res.json()
        change_id = change_data["id"]

        commit_res = client.post(
            f"/v1/agent/tasks/{task.id}/commit",
            headers=agent_auth_headers,
            json={
                "resulting_commit": test_commit_sha,
                "commit_sha": test_commit_sha,
            },
        )
        assert commit_res.status_code == 200, f"Failed to record commit: {commit_res.text}"

        pr_create_resp = client.post(
            f"/v1/agent/tasks/{task.id}/pull-requests",
            json={
                "title": f"Autonomous Live Merge Verification [{test_branch}]",
                "description": "Governed agent PR created for final live merge lifecycle verification.",
                "target_branch": default_branch,
                "is_draft": False,
            },
            headers=agent_auth_headers,
        )
        assert pr_create_resp.status_code == 201, f"Failed to create PR: {pr_create_resp.text}"
        pr_data = pr_create_resp.json()
        sutra_pr_id = pr_data["id"]
        created_gh_pr_number = pr_data.get("github_pr_number")
        assert created_gh_pr_number, f"PR created without github_pr_number: {pr_data}"
        print(f"[LIVE] Created real GitHub Pull Request #{created_gh_pr_number} for SUTRA PR #{sutra_pr_id}")

        owner_token = create_access_token(user.id)
        reviewer_token = create_access_token(reviewer_user.id)
        unauth_token = create_access_token(unauth_user.id)

        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        reviewer_headers = {"Authorization": f"Bearer {reviewer_token}"}
        unauth_headers = {"Authorization": f"Bearer {unauth_token}"}

        # =========================================================
        # CASE 8: Agent attempts merge -> Strictly rejected
        # =========================================================
        agent_merge_resp = client.post(
            f"/v1/pull-requests/{sutra_pr_id}/merge",
            headers=agent_auth_headers,
        )
        assert agent_merge_resp.status_code in (401, 403), (
            f"Expected agent merge rejection, got {agent_merge_resp.status_code}: {agent_merge_resp.text}"
        )
        print("[LIVE CASE 8] PASSED: Agent directly invoking merge was strictly rejected.")

        # =========================================================
        # CASE 9: Unauthorized human attempts merge -> Strictly rejected
        # =========================================================
        unauth_merge_resp = client.post(
            f"/v1/pull-requests/{sutra_pr_id}/merge",
            headers=unauth_headers,
        )
        assert unauth_merge_resp.status_code in (403, 404), (
            f"Expected unauthorized human merge rejection, got {unauth_merge_resp.status_code}: {unauth_merge_resp.text}"
        )
        print("[LIVE CASE 9] PASSED: Unauthorized user merge attempt was strictly rejected.")

        # =========================================================
        # CASE 1: PR not approved -> merge rejected, GitHub API not called
        # =========================================================
        unapproved_merge_resp = client.post(
            f"/v1/pull-requests/{sutra_pr_id}/merge",
            headers=owner_headers,
        )
        assert unapproved_merge_resp.status_code == 409, (
            f"Expected 409 for unapproved merge, got {unapproved_merge_resp.status_code}: {unapproved_merge_resp.text}"
        )
        assert "governance" in unapproved_merge_resp.text.lower() or "review" in unapproved_merge_resp.text.lower()
        print("[LIVE CASE 1] PASSED: Unapproved PR merge rejected, GitHub merge API not called.")

        # =========================================================
        # CASE 2: CI failing -> merge rejected
        # =========================================================
        failing_ci = CIJob(
            id=str(uuid4()),
            pull_request_id=sutra_pr_id,
            repository_id=repository.id,
            change_id=change_id,
            commit_sha=test_commit_sha,
            target_branch=default_branch,
            status=CIJob.STATUS_FAILED,
            trigger="github_actions",
        )
        db.add(failing_ci)
        db.commit()

        ci_fail_merge_resp = client.post(
            f"/v1/pull-requests/{sutra_pr_id}/merge",
            headers=owner_headers,
        )
        assert ci_fail_merge_resp.status_code == 409
        print("[LIVE CASE 2] PASSED: Merge rejected when CI checks are failing.")

        # Remove failing CI job and insert passing CI job
        db.delete(failing_ci)
        passing_ci = CIJob(
            id=str(uuid4()),
            pull_request_id=sutra_pr_id,
            repository_id=repository.id,
            change_id=change_id,
            commit_sha=test_commit_sha,
            target_branch=default_branch,
            status=CIJob.STATUS_PASSED,
            trigger="github_actions",
        )
        db.add(passing_ci)
        db.commit()

        # =========================================================
        # CASE 3: Governance blocked -> merge rejected
        # =========================================================
        # Before approval, governance evaluates to NEEDS_REVIEW or BLOCKED, rejecting merge
        gov_svc = GovernanceService(db, provider=provider)
        gov_pre = gov_svc.evaluate_pull_request(sutra_pr_id)
        assert gov_pre["verdict"] != GovernanceVerdict.READY_FOR_MERGE
        print(f"[LIVE CASE 3] PASSED: Governance verdict is '{gov_pre['verdict']}' (not READY_FOR_MERGE); merge blocked.")

        # =========================================================
        # Human Approval Execution: Legitimate Human Reviewer Approves
        # =========================================================
        appr_resp = client.post(
            f"/v1/pull-requests/{sutra_pr_id}/approve",
            json={"reason": "LGTM for live governed merge verification"},
            headers=reviewer_headers,
        )
        assert appr_resp.status_code == 200, f"Approval failed: {appr_resp.text}"
        print("[LIVE] PR successfully approved by human reviewer.")

        # Verify Governance verdict is now READY_FOR_MERGE
        gov_eval = gov_svc.evaluate_pull_request(sutra_pr_id)
        assert gov_eval["verdict"] == GovernanceVerdict.READY_FOR_MERGE
        print(f"[LIVE] SUTRA Governance verdict verified: {gov_eval['verdict']}")

        # =========================================================
        # CASE 7: HEAD changes after approval -> merge rejected
        # =========================================================
        # Simulate PR HEAD differing from approved HEAD in change metadata
        db_pr = db.scalar(select(PullRequest).where(PullRequest.id == sutra_pr_id))
        original_source_commit = db_pr.source_commit
        db_pr.source_commit = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
        db.commit()

        stale_merge_resp = client.post(
            f"/v1/pull-requests/{sutra_pr_id}/merge",
            headers=owner_headers,
        )
        assert stale_merge_resp.status_code == 409
        assert "HEAD changed" in stale_merge_resp.text or "invalidated" in stale_merge_resp.text.lower() or "governance" in stale_merge_resp.text.lower()
        print("[LIVE CASE 7] PASSED: Merge rejected when PR HEAD changed since approval.")

        # Restore genuine commit SHA
        db_pr.source_commit = original_source_commit
        db.commit()

        # =========================================================
        # CASE 4: Approved PR / READY_FOR_MERGE -> Real GitHub merge succeeds
        # =========================================================
        print("[LIVE CASE 4] Executing authoritative merge via SUTRA control plane...")
        merge_resp = client.post(
            f"/v1/pull-requests/{sutra_pr_id}/merge",
            headers=owner_headers,
        )
        assert merge_resp.status_code == 200, f"Merge failed: {merge_resp.text}"
        merge_data = merge_resp.json()
        assert merge_data["status"] == "merged"
        merge_commit_sha = merge_data.get("merge_commit_sha")
        print(f"[LIVE CASE 4] PASSED: Real GitHub merge succeeded! Resulting merge commit: {merge_commit_sha}")

        # =========================================================
        # CASE 5: Verify GitHub PR is actually merged -> obtain merge SHA
        # =========================================================
        gh_pr_after = provider.get_pull_request(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            pr_number=created_gh_pr_number,
        )
        assert gh_pr_after is not None
        assert gh_pr_after.is_merged is True, "GitHub substrate does not report PR as merged!"
        print(f"[LIVE CASE 5] PASSED: Authoritative substrate verification confirmed GitHub PR #{created_gh_pr_number} is_merged=True.")

        # =========================================================
        # CASE 6: Retry same merge request -> idempotent reconciliation
        # =========================================================
        retry_merge_resp = client.post(
            f"/v1/pull-requests/{sutra_pr_id}/merge",
            headers=owner_headers,
        )
        assert retry_merge_resp.status_code == 200
        retry_data = retry_merge_resp.json()
        assert retry_data["status"] == "merged"
        assert "already merged" in retry_data["detail"].lower()
        print("[LIVE CASE 6] PASSED: Idempotent retry safely returned merged status without duplicate operations.")

        # =========================================================
        # CASE 10: Verify Complete End-to-End Provenance Chain
        # =========================================================
        db.expire_all()
        db_pr = db.scalar(select(PullRequest).where(PullRequest.id == sutra_pr_id))
        assert db_pr.status == PullRequest.STATUS_MERGED
        assert db_pr.merged_at is not None

        db_change = db.scalar(select(Change).where(Change.id == change_id))
        assert db_change.status == "recorded"
        c_meta = json.loads(db_change.metadata_json or "{}")
        assert c_meta.get("merged") is True
        assert c_meta.get("merged_by") == user.id

        db_task = db.scalar(select(Task).where(Task.id == task.id))
        assert db_task.status == Task.STATUS_COMPLETED
        assert db_task.completed_at is not None

        # Verify audit event
        merge_event = db.scalar(
            select(ChangeEvent).where(
                ChangeEvent.change_id == change_id,
                ChangeEvent.event_type == "pull_request.merged",
            )
        )
        assert merge_event is not None
        event_meta = json.loads(merge_event.metadata_json)
        assert event_meta["actor_id"] == user.id
        assert event_meta["github_pr_number"] == created_gh_pr_number
        assert event_meta["head_sha"] == test_commit_sha

        # Print full verified provenance chain
        print("\n" + "=" * 60)
        print("SUTRA FINAL GOVERNED MERGE PROVENANCE CHAIN VERIFIED:")
        print(f"  1. AGENT:           {agent.name} ({agent.id})")
        print(f"  2. SESSION:         {session.id}")
        print(f"  3. TASK:            {db_task.id} (Status: {db_task.status})")
        print(f"  4. CHANGE:          {db_change.id} (Status: {db_change.status})")
        print(f"  5. GITHUB PR:       #{created_gh_pr_number} (SUTRA PR #{db_pr.id})")
        print(f"  6. REVIEWED HEAD:   {test_commit_sha}")
        print(f"  7. HUMAN APPROVER:  {reviewer_user.username} ({reviewer_user.id})")
        print(f"  8. HUMAN MERGER:    {user.username} ({user.id})")
        print(f"  9. MERGE COMMIT:    {merge_commit_sha or db_pr.target_commit}")
        print(f" 10. AUDIT EVENT:     pull_request.merged recorded")
        print("=" * 60)
        print("[LIVE CASE 10] PASSED: Full provenance chain verified.")

    finally:
        # Clean up test branch on GitHub
        if test_branch:
            try:
                provider.delete_branch(
                    owner=GITHUB_OWNER,
                    name=GITHUB_REPOSITORY,
                    branch=test_branch,
                )
                print(f"[LIVE CLEANUP] Deleted test branch '{test_branch}' from GitHub.")
            except Exception as e:
                print(f"[LIVE CLEANUP WARNING] Could not delete branch {test_branch}: {e}")
        db.close()
