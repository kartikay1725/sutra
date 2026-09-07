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
from app.models.pull_request import PullRequest
from app.models.ci_job import CIJob


GITHUB_OWNER = "kartikay1725"
GITHUB_REPOSITORY = "dam-project"


def test_live_agent_pull_request_checks_e2e():
    """
    Live Agent Pull Request -> Checks / CI Lifecycle E2E against real GitHub substrate:

        Real GitHub repository (kartikay1725/dam-project)
              ↓
        Real SUTRA repository mapping
              ↓
        Registered Agent + Actor
              ↓
        Governed AgentSession
              ↓
        Claimed Task
              ↓
        Real Recorded SUTRA Change (with real substrate commit)
              ↓
        POST /v1/agent/tasks/{task_id}/pull-requests
              ↓
        Real GitHub Pull Request created with SUTRA Agent Provenance
              ↓
        Real GitHub Check Run created on the PR HEAD commit SHA
              ↓
        SUTRA reads/synchronizes check state from GitHub substrate
              ↓
        GET /v1/pull-requests/{id}/checks exposes normalized check contract:
            - head_sha accurately isolated to PR HEAD commit
            - check name, status, conclusion, GitHub details URL
            - overall_status: "passed"
            - governance_verdict: "READY FOR GOVERNANCE"
              ↓
        Safe GitHub cleanup (close PR + delete test branch)
    """

    db = SessionLocal()

    user = None
    user_actor = None
    repository = None
    agent = None
    actor = None
    session = None
    task = None
    change_record = None
    change_id = None
    pr_record = None
    test_branch = f"agent-ci-test-{uuid4().hex[:8]}"
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
        # 2. Verify the real GitHub repository and master branch
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
        # 3. Create temporary branch on GitHub for this PR and commit a change
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
            path=f"docs/ci-tests/{test_branch}.md",
            message=f"feat(ci): automated check verification commit for {test_branch}",
            content=f"# CI Verification Pipeline\nAutonomous Agent PR CI verification for task {test_branch}.\n".encode("utf-8"),
            branch=test_branch,
        )
        test_commit_sha = file_res["commit"]["sha"]
        print(f"Committed file to {test_branch} (SHA: {test_commit_sha})")

        # =========================================================
        # 4. Create temporary SUTRA records
        # =========================================================

        user = User(
            id=str(uuid4()),
            username=f"live_ci_user_{uuid4().hex[:8]}",
            email=f"live_ci_{uuid4().hex[:8]}@example.com",
            password_hash=hash_password("password123"),
        )
        db.add(user)
        db.flush()

        user_actor = Actor(
            id=user.id,
            owner_id=user.id,
            type="human",
            name=user.username,
            capabilities=json.dumps(["repository.read", "repository.write", "change.create"]),
        )
        db.add(user_actor)
        db.flush()

        repository = Repository(
            id=str(uuid4()),
            owner_id=user.id,
            name=GITHUB_REPOSITORY,
            slug=GITHUB_REPOSITORY,
            description="Temporary SUTRA mapping for live Agent PR CI Checks E2E",
            visibility="private",
            storage_key=f"github-ci-test/{uuid4().hex}",
            provider_type="github",
            provider_owner=GITHUB_OWNER,
            external_id=f"live-e2e-ci-{uuid4().hex}",
            github_installation_id=(
                settings.github_installation_id
                if hasattr(settings, "github_installation_id")
                else 158557464
            ),
            default_branch=default_branch,
            settings={},
        )
        db.add(repository)
        db.flush()

        agent = Agent(
            id=str(uuid4()),
            owner_id=user.id,
            name=f"Atlas-CI-{uuid4().hex[:6]}",
            description="Temporary live Agent CI Checks agent",
            provider="test",
            model="test-model",
            token_hash=hash_password(f"unused-token-{uuid4().hex}"),
            token_prefix=uuid4().hex[:16],
            status="active",
            is_active=True,
        )
        db.add(agent)
        db.flush()

        actor = Actor(
            id=agent.id,
            type="agent",
            name=agent.name,
            owner_id=user.id,
            capabilities=json.dumps([
                "repository.read",
                "repository.write",
                "change.create",
                "change.commit",
                "change.conflict.read",
            ]),
        )
        db.add(actor)
        db.flush()

        session_token = f"sutra_session_{uuid4().hex}_{uuid4().hex}"
        session = AgentSession(
            id=str(uuid4()),
            agent_id=agent.id,
            token_hash=hash_password(session_token),
            token_prefix=session_token[:32],
            status="active",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.flush()

        task = Task(
            id=str(uuid4()),
            repository_id=repository.id,
            created_by=user.id,
            assigned_agent_id=agent.id,
            assigned_user_id=None,
            claimed_by_session_id=session.id,
            lease_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            resulting_change_id=None,
            resulting_pull_request_id=None,
            title=f"Live Agent CI Checks Task {uuid4().hex[:8]}",
            description="Autonomous feature development with GitHub Pull Request CI verification.",
            status=Task.STATUS_IN_PROGRESS,
            priority=Task.PRIORITY_HIGH,
            priority_index=0.0,
            task_type=Task.TYPE_FEATURE,
            source="live_test",
        )
        db.add(task)
        db.commit()

        print(f"SUTRA Repos ID: {repository.id}, Agent: {agent.id}, Session: {session.id}, Task: {task.id}")

        # =========================================================
        # 5. Create Change and Record Commit
        # =========================================================

        with TestClient(app) as client:
            agent_auth_headers = {
                "Authorization": f"Bearer {session_token}",
            }

            ch_res = client.post(
                f"/v1/agent/tasks/{task.id}/changes",
                headers=agent_auth_headers,
                json={
                    "intent": f"Automated CI check delivery for {test_branch}",
                    "branch": test_branch,
                    "base_branch": default_branch,
                },
            )
            assert ch_res.status_code == 201, f"Failed to create change: {ch_res.text}"
            change_data = ch_res.json()
            change_id = change_data["id"]
            print(f"Created SUTRA Change: {change_id}")

            # Record commit
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

            # =========================================================
            # 6. Agent Creates Real GitHub Pull Request
            # =========================================================

            pr_title = f"feat(agent-ci): automated CI check verification ({test_branch})"
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

            pr_resp = client.post(
                f"/v1/agent/tasks/{task.id}/pull-requests",
                json=pr_payload,
                headers=agent_auth_headers,
            )
            assert pr_resp.status_code == 201, f"Failed to create PR: {pr_resp.text}"
            pr_data = pr_resp.json()
            created_gh_pr_number = pr_data.get("github_pr_number")
            sutra_pr_id = pr_data["id"]

            print(f"Created real GitHub PR #{created_gh_pr_number} (SUTRA ID: {sutra_pr_id})")
            print(f"GitHub URL: {pr_data.get('github_html_url')}")

            # =========================================================
            # 7. Create Authoritative Check Run on Real GitHub Substrate
            # =========================================================

            check_run_name = "sutra/ci-verification"
            created_check_run = provider.create_check_run(
                owner=GITHUB_OWNER,
                name=GITHUB_REPOSITORY,
                check_name=check_run_name,
                head_sha=test_commit_sha,
                status="completed",
                conclusion="success",
                title="SUTRA Automated CI Check",
                summary="All automated unit and integration tests passed cleanly.",
                details_url=f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPOSITORY}/pull/{created_gh_pr_number}",
            )
            assert created_check_run, "Failed to create real GitHub check run"
            print(f"Created real GitHub check run '{check_run_name}' on HEAD commit {test_commit_sha[:10]}: id={created_check_run.get('id')}")

            # =========================================================
            # 8. Query SUTRA PR Checks API & Verify Contract
            # =========================================================

            user_token = create_access_token(user.id)
            user_auth_headers = {"Authorization": f"Bearer {user_token}"}

            checks_resp = client.get(
                f"/v1/pull-requests/{sutra_pr_id}/checks",
                headers=user_auth_headers,
            )
            assert checks_resp.status_code == 200, f"Failed to get PR checks: {checks_resp.text}"
            checks_data = checks_resp.json()

            print()
            print("=== SUTRA AUTHORITATIVE CHECKS CONTRACT ===")
            print(json.dumps(checks_data, indent=2))

            assert checks_data["pull_request_id"] == sutra_pr_id
            assert checks_data["head_sha"] == test_commit_sha
            assert checks_data["summary"]["total"] >= 1
            assert checks_data["summary"]["passed"] >= 1
            assert checks_data["summary"]["failed"] == 0
            assert checks_data["overall_status"] == "passed"
            assert checks_data["governance_verdict"] == "READY FOR GOVERNANCE"

            matched_check = next(
                (c for c in checks_data["checks"] if c["name"] == check_run_name),
                None,
            )
            assert matched_check is not None, f"Check '{check_run_name}' not found in checks response"
            assert matched_check["conclusion"] == "success"
            assert matched_check["sutra_state"] == "passed"
            assert matched_check["source"] == "github"

            # Verify enriched PR response also includes checks_summary and checks_verdict
            pr_detail_resp = client.get(
                f"/v1/pull-requests/{sutra_pr_id}",
                headers=user_auth_headers,
            )
            assert pr_detail_resp.status_code == 200
            pr_detail = pr_detail_resp.json()
            assert pr_detail["checks_summary"] is not None
            assert pr_detail["checks_summary"]["passed"] >= 1
            assert pr_detail["checks_verdict"] == "READY FOR GOVERNANCE"

            print()
            print("Successfully verified Authoritative Checks & Governance Verdict against real GitHub Substrate!")

    finally:
        # =========================================================
        # 9. Clean up GitHub and SUTRA Resources Safely
        # =========================================================

        print()
        print("Cleaning up live test resources...")

        # Close GitHub PR if created
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

        # Delete test branch if created
        try:
            provider.delete_branch(
                owner=GITHUB_OWNER,
                name=GITHUB_REPOSITORY,
                branch=test_branch,
            )
            print(f"Deleted GitHub test branch: {test_branch}")
        except Exception as e:
            print(f"Warning: Failed to delete GitHub test branch: {e}")

        # Clean SUTRA DB
        try:
            if change_id:
                db.query(CIJob).filter(CIJob.change_id == change_id).delete()
                db.query(PullRequest).filter(PullRequest.source_change_id == change_id).delete()
                db.query(Change).filter(Change.id == change_id).delete()
            if pr_record:
                db.delete(pr_record)
            if change_record:
                db.delete(change_record)
            if task:
                db.query(CIJob).filter(CIJob.pull_request_id == task.resulting_pull_request_id).delete()
                db.query(PullRequest).filter(PullRequest.id == task.resulting_pull_request_id).delete()
                db.query(Change).filter(Change.id == task.resulting_change_id).delete()
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
            if user:
                db.execute(text("DELETE FROM notifications WHERE user_id = :uid"), {"uid": user.id})
                db.delete(user)
            db.commit()
            print("Cleaned up temporary SUTRA database records.")
        except Exception as e:
            db.rollback()
            print(f"Warning during SUTRA DB cleanup: {e}")
        finally:
            db.close()


if __name__ == "__main__":
    test_live_agent_pull_request_checks_e2e()
