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
from app.models.task_event import TaskEvent
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.pull_request import PullRequest


GITHUB_OWNER = "kartikay1725"
GITHUB_REPOSITORY = "dam-project"


def test_live_agent_pull_request_e2e():
    """
    Live Agent Pull Request E2E against real GitHub substrate:

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
        SUTRA PullRequest persistence + Change & Task linkage
              ↓
        Lightweight SUTRA PR API response with GitHub URL and Agent context
              ↓
        Safe GitHub cleanup (close PR + delete test branch)
    """

    db = SessionLocal()

    user = None
    repository = None
    agent = None
    actor = None
    session = None
    task = None
    change_record = None
    change_id = None
    pr_record = None
    test_branch = f"agent-pr-test-{uuid4().hex[:8]}"
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
            path=f"docs/agent-tasks/{test_branch}.md",
            message=f"feat(agent): autonomous telemetry update for {test_branch}",
            content=f"# Hydro Telemetry Pipeline\nAutonomous Agent PR delivery for task {test_branch}.\n".encode("utf-8"),
            branch=test_branch,
        )
        test_commit_sha = file_res["commit"]["sha"]
        print(f"Committed file to {test_branch} (SHA: {test_commit_sha})")

        # =========================================================
        # 4. Create temporary SUTRA records
        # =========================================================

        user = User(
            id=str(uuid4()),
            username=f"live_pr_user_{uuid4().hex[:8]}",
            email=f"live_pr_{uuid4().hex[:8]}@example.com",
            password_hash=hash_password("password123"),
        )
        db.add(user)
        db.flush()

        user_actor = Actor(
            id=user.id,
            type="human",
            name=user.username,
            owner_id=user.id,
            capabilities=json.dumps([
                "repository.read",
                "repository.write",
                "change.create",
            ]),
        )
        db.add(user_actor)
        db.flush()

        repository = Repository(
            id=str(uuid4()),
            owner_id=user.id,
            name=GITHUB_REPOSITORY,
            slug=GITHUB_REPOSITORY,
            description="Temporary SUTRA mapping for live Agent PR E2E",
            visibility="private",
            storage_key=f"github-pr-test/{uuid4().hex}",
            provider_type="github",
            provider_owner=GITHUB_OWNER,
            external_id=f"live-e2e-pr-{uuid4().hex}",
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
            name=f"Atlas-PR-{uuid4().hex[:6]}",
            description="Temporary live Agent PR E2E agent",
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
            title=f"Live Agent PR Task {uuid4().hex[:8]}",
            description="Autonomous feature development with GitHub Pull Request delivery.",
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
            ch_res = client.post(
                f"/v1/agent/tasks/{task.id}/changes",
                headers={"Authorization": f"Bearer {session_token}"},
                json={
                    "intent": f"Deliver {task.title}",
                    "branch": test_branch,
                    "base_branch": default_branch,
                },
            )
            assert ch_res.status_code == 201, ch_res.text
            change_id = ch_res.json()["id"]

            commit_res = client.post(
                f"/v1/agent/tasks/{task.id}/commit",
                headers={"Authorization": f"Bearer {session_token}"},
                json={
                    "resulting_commit": test_commit_sha,
                    "commit_sha": test_commit_sha,
                },
            )
            assert commit_res.status_code == 200, commit_res.text
            assert commit_res.json()["status"] == "recorded"

        # =========================================================
        # 6. Execute Agent Pull Request Creation
        # =========================================================

        print("Calling POST /v1/agent/tasks/{task_id}/pull-requests...")
        with TestClient(app) as client:
            pr_res = client.post(
                f"/v1/agent/tasks/{task.id}/pull-requests",
                headers={"Authorization": f"Bearer {session_token}"},
                json={
                    "title": f"Feature: {task.title}",
                    "description": "Automated delivery of flood prediction enhancement.",
                    "target_branch": default_branch,
                },
            )
            print(f"PR HTTP STATUS: {pr_res.status_code}")
            print(f"PR RESPONSE: {pr_res.text}")
            assert pr_res.status_code == 201, pr_res.text
            pr_payload = pr_res.json()

        # =========================================================
        # 7. Validate Live GitHub PR Integration
        # =========================================================

        pr_id = pr_payload["id"]
        assert pr_payload["status"] == "open"
        assert pr_payload["repository_id"] == repository.id
        assert pr_payload["source_change_id"] == change_id
        assert pr_payload["task_id"] == task.id
        assert pr_payload["agent_id"] == agent.id
        assert pr_payload["agent_name"] == agent.name
        assert pr_payload["agent_session_id"] == session.id

        # GitHub PR number & URL must be populated
        gh_number = pr_payload.get("github_pr_number")
        gh_url = pr_payload.get("github_html_url")
        assert gh_number is not None, f"Expected real GitHub PR number in response: {pr_payload}"
        assert gh_url and "github.com" in gh_url, f"Expected real GitHub PR URL: {gh_url}"
        created_gh_pr_number = gh_number

        print(f"Created REAL GitHub PR #{gh_number}: {gh_url}")

        # Fetch the PR directly from GitHub substrate to verify body & provenance
        gh_pr_obj = provider.get_pull_request(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            pr_number=gh_number,
        )
        assert gh_pr_obj is not None
        assert gh_pr_obj.number == gh_number
        assert gh_pr_obj.head_ref == test_branch
        assert gh_pr_obj.base_ref == default_branch
        assert "SUTRA Agent Provenance" in (gh_pr_obj.body or "")
        assert agent.name in (gh_pr_obj.body or "")
        assert session.id in (gh_pr_obj.body or "")
        print("Verified GitHub PR substrate object and provenance footer.")

        # =========================================================
        # 8. Validate Task & Change Linkage in Database
        # =========================================================

        db.expire_all()
        refreshed_task = db.scalar(select(Task).where(Task.id == task.id))
        assert refreshed_task.resulting_pull_request_id == pr_id, (
            f"Expected task.resulting_pull_request_id == {pr_id}, got {refreshed_task.resulting_pull_request_id}"
        )

        refreshed_change = db.scalar(select(Change).where(Change.id == change_id))
        change_meta = json.loads(refreshed_change.metadata_json or "{}")
        assert change_meta.get("pull_request_id") == pr_id
        assert change_meta.get("github_pr_number") == gh_number
        assert change_meta.get("github_pr_url") == gh_url

        events = db.scalars(
            select(TaskEvent).where(
                TaskEvent.task_id == task.id,
                TaskEvent.event_type == "task.pull_request_created",
            )
        ).all()
        assert len(events) >= 1

        # =========================================================
        # 9. Verify SUTRA PR GET endpoint returns enriched context
        # =========================================================

        user_token = create_access_token(user.id)
        with TestClient(app) as client:
            get_pr_res = client.get(
                f"/v1/pull-requests/{pr_id}",
                headers={"Authorization": f"Bearer {user_token}"},
            )
            assert get_pr_res.status_code == 200, get_pr_res.text
            detail = get_pr_res.json()
            assert detail["id"] == pr_id
            assert detail["github_pr_number"] == gh_number
            assert detail["github_html_url"] == gh_url
            assert detail["task_id"] == task.id
            assert detail["agent_id"] == agent.id
            assert detail["agent_session_id"] == session.id
            assert detail["repository_name"] == GITHUB_REPOSITORY

        print("All Live PR assertions passed successfully!")

    finally:
        # =========================================================
        # Safe Cleanup
        # =========================================================
        print("\nCleaning up live test resources...")

        # 1. Close GitHub PR
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

        # 2. Delete test branch on GitHub
        try:
            provider.delete_branch(
                owner=GITHUB_OWNER,
                name=GITHUB_REPOSITORY,
                branch=test_branch,
            )
            print(f"Deleted GitHub test branch: {test_branch}")
        except Exception as e:
            print(f"Warning: Failed to delete GitHub branch {test_branch}: {e}")

        # 3. Clean up temporary SUTRA records in reverse order
        try:
            if task:
                db.query(TaskEvent).filter(TaskEvent.task_id == task.id).delete()
                db.query(Task).filter(Task.id == task.id).delete()

            if change_id:
                db.query(ChangeEvent).filter(ChangeEvent.change_id == change_id).delete()
                db.query(PullRequest).filter(PullRequest.source_change_id == change_id).delete()
                db.query(Change).filter(Change.id == change_id).delete()

            if session:
                db.query(AgentSession).filter(AgentSession.id == session.id).delete()

            if actor:
                db.query(Actor).filter(Actor.id == actor.id).delete()

            if agent:
                db.query(Agent).filter(Agent.id == agent.id).delete()

            if repository:
                db.query(Repository).filter(Repository.id == repository.id).delete()

            if user:
                from app.models.notification import Notification
                db.query(Notification).filter(Notification.user_id == user.id).delete()
                db.query(Actor).filter(Actor.id == user.id).delete()
                db.query(User).filter(User.id == user.id).delete()

            db.commit()
            print("Cleaned up temporary SUTRA database records.")
        except Exception as e:
            db.rollback()
            print(f"Cleanup error: {e}")
        finally:
            db.close()
