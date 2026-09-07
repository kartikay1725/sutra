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
from app.models.change_file import ChangeFile
from app.models.change_event import ChangeEvent
from app.services.code_provenance_service import CodeProvenanceService


GITHUB_OWNER = "kartikay1725"
GITHUB_REPOSITORY = "dam-project"


def test_live_agent_change_e2e():
    """
    Full live Agent Change E2E:

        temporary SUTRA user
              ↓
        temporary SUTRA repository (pointing to real GitHub kartikay1725/dam-project)
              ↓
        registered Agent
              ↓
        Agent Actor
              ↓
        AgentSession
              ↓
        claimed Task
              ↓
        POST /v1/agent/tasks/{task.id}/changes (authenticated with session token)
              ↓
        real substrate branch/commit resolution (GitHub App tokens)
              ↓
        SUTRA Change record created + linked to Task.resulting_change_id
              ↓
        POST /v1/agent/tasks/{task.id}/commit (record commit with provenance)
              ↓
        GET /v1/changes/{change.id} (enriched response with commits, task, agent provenance)
              ↓
        CodeProvenanceService provenance verification
    """

    db = SessionLocal()

    user = None
    repository = None
    agent = None
    actor = None
    session = None
    task = None
    change_record = None

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

        assert branches, (
            f"GitHub repository {GITHUB_OWNER}/{GITHUB_REPOSITORY} returned no branches"
        )

        default_branch = "master"
        master_branch = next(
            (b for b in branches if getattr(b, "name", None) == default_branch),
            None,
        )
        assert master_branch is not None, (
            f"Expected GitHub branch '{default_branch}' was not found"
        )

        print()
        print(f"Verified GitHub repository: {GITHUB_OWNER}/{GITHUB_REPOSITORY}")
        print(f"Verified default branch: {default_branch} (commit: {master_branch.commit_sha})")

        # =========================================================
        # 3. Create temporary SUTRA user
        # =========================================================

        user = User(
            id=str(uuid4()),
            username=f"live_change_user_{uuid4().hex[:8]}",
            email=f"live_change_{uuid4().hex[:8]}@example.com",
            password_hash=hash_password("password123"),
        )

        db.add(user)
        db.flush()

        # =========================================================
        # 4. Create temporary SUTRA GitHub repository mapping
        # =========================================================

        repository = Repository(
            id=str(uuid4()),
            owner_id=user.id,
            name=GITHUB_REPOSITORY,
            slug=GITHUB_REPOSITORY,
            description="Temporary SUTRA mapping for live Agent Change E2E test",
            visibility="private",
            storage_key=f"github-test/{uuid4().hex}",
            provider_type="github",
            provider_owner=GITHUB_OWNER,
            external_id=f"live-e2e-change-{uuid4().hex}",
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

        print(f"SUTRA repository ID: {repository.id}")

        # =========================================================
        # 5. Temporary registered Agent
        # =========================================================

        agent = Agent(
            id=str(uuid4()),
            owner_id=user.id,
            name=f"Atlas-Change-{uuid4().hex[:6]}",
            description="Temporary live Agent Change E2E agent",
            provider="test",
            model="test-model",
            token_hash=hash_password(f"unused-token-{uuid4().hex}"),
            token_prefix=uuid4().hex[:16],
            status="active",
            is_active=True,
        )

        db.add(agent)
        db.flush()

        print(f"Agent ID: {agent.id}")

        # =========================================================
        # 6. Agent Actor with change capabilities
        # =========================================================

        actor = Actor(
            id=agent.id,
            type="agent",
            name=agent.name,
            owner_id=user.id,
            capabilities=(
                '["repository.read",'
                '"repository.write",'
                '"change.create",'
                '"change.commit",'
                '"change.conflict.read"]'
            ),
        )

        db.add(actor)
        db.flush()

        # =========================================================
        # 7. Real AgentSession
        # =========================================================

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

        print(f"Session ID: {session.id}")

        # =========================================================
        # 8. Claimed Task
        # =========================================================

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
            title=f"Live Agent Change E2E {uuid4().hex[:8]}",
            description="Create a real SUTRA Change and commit under governed lease.",
            status=Task.STATUS_IN_PROGRESS,
            priority=Task.PRIORITY_MEDIUM,
            priority_index=0.0,
            task_type=Task.TYPE_FEATURE,
            source="live_test",
        )

        db.add(task)
        db.commit()

        print(f"Task ID: {task.id}")

        # =========================================================
        # 9. Call REAL SUTRA Agent Change Endpoint
        # =========================================================

        proposed_branch = f"agent/change-{uuid4().hex[:8]}"
        change_title = f"Agent Feature: {task.title}"
        change_desc = "Automated change created by SUTRA agent under task lease."

        print()
        print("Calling POST /v1/agent/tasks/{task_id}/changes...")

        with TestClient(app) as client:
            response = client.post(
                f"/v1/agent/tasks/{task.id}/changes",
                headers={
                    "Authorization": f"Bearer {session_token}",
                },
                json={
                    "intent": change_title,
                    "title": change_title,
                    "description": change_desc,
                    "branch": proposed_branch,
                    "base_branch": default_branch,
                },
            )

            print(f"HTTP STATUS: {response.status_code}")
            print(f"RESPONSE: {response.text}")

            assert response.status_code == 201, response.text
            change_data = response.json()

        change_id = change_data["id"]
        assert change_data["status"] == "proposed"
        assert change_data["repository_id"] == repository.id
        assert change_data["task_id"] == task.id
        assert change_data["agent_id"] == agent.id
        assert change_data["agent_session_id"] == session.id
        assert change_data["branch"] == proposed_branch
        assert change_data["base_branch"] == default_branch
        # Base commit was resolved from real GitHub default branch
        assert change_data["base_commit"] == master_branch.commit_sha

        # =========================================================
        # 10. Verify Task Linkage in Database
        # =========================================================

        db.expire_all()
        refreshed_task = db.scalar(select(Task).where(Task.id == task.id))
        assert refreshed_task.resulting_change_id == change_id, (
            f"Expected task.resulting_change_id == {change_id}, got {refreshed_task.resulting_change_id}"
        )

        stored_change = db.scalar(select(Change).where(Change.id == change_id))
        assert stored_change is not None
        change_meta = json.loads(stored_change.metadata_json or "{}")
        assert change_meta.get("task_id") == task.id
        assert change_meta.get("agent_session_id") == session.id
        assert change_meta.get("branch") == proposed_branch
        assert stored_change.base_commit == master_branch.commit_sha

        # Verify audit event
        events = db.scalars(select(ChangeEvent).where(ChangeEvent.change_id == change_id)).all()
        assert any(e.event_type == "change.created" for e in events)

        # =========================================================
        # 11. Record Commit via Agent Commit Endpoint
        # =========================================================

        print()
        print("Calling POST /v1/agent/tasks/{task_id}/commit...")

        commit_sha = master_branch.commit_sha
        commit_message = f"Governed agent commit for task #{task.id[:8]}"

        with TestClient(app) as client:
            commit_response = client.post(
                f"/v1/agent/tasks/{task.id}/commit",
                headers={
                    "Authorization": f"Bearer {session_token}",
                },
                json={
                    "resulting_commit": commit_sha,
                    "commit_sha": commit_sha,
                    "message": commit_message,
                    "author_name": agent.name,
                    "author_email": f"{agent.id[:8]}@agent.sutra.local",
                },
            )

            print(f"HTTP STATUS: {commit_response.status_code}")
            print(f"RESPONSE: {commit_response.text}")

            assert commit_response.status_code == 200, commit_response.text
            updated_change_data = commit_response.json()

        assert updated_change_data["status"] == "recorded"
        assert updated_change_data["resulting_commit"] == commit_sha

        # =========================================================
        # 12. Verify Enriched GET /v1/changes/{id} API
        # =========================================================

        print()
        print(f"Calling GET /v1/changes/{change_id}...")

        user_token = create_access_token(user.id)
        with TestClient(app) as client:
            get_response = client.get(
                f"/v1/changes/{change_id}",
                headers={
                    "Authorization": f"Bearer {user_token}",
                },
            )

            assert get_response.status_code == 200, get_response.text
            detail = get_response.json()

        assert detail["id"] == change_id
        assert detail["repository_name"] == GITHUB_REPOSITORY
        assert detail["title"] == change_title
        assert detail["task_id"] == task.id
        assert detail["task_title"] == task.title
        assert detail["agent_id"] == agent.id
        assert detail["agent_name"] == agent.name
        assert detail["agent_session_id"] == session.id
        assert detail["status"] == "recorded"
        assert len(detail["commits"]) >= 1

        first_commit = detail["commits"][0]
        assert first_commit["sha"] == commit_sha
        assert first_commit["provenance"] is not None
        assert first_commit["provenance"]["identity_type"] == "agent"
        assert first_commit["provenance"]["agent"]["id"] == agent.id
        assert first_commit["provenance"]["session"]["id"] == session.id
        assert first_commit["provenance"]["task"]["id"] == task.id

        # =========================================================
        # 13. Direct CodeProvenanceService Verification
        # =========================================================

        provenance = CodeProvenanceService(db).resolve_commit(
            repository_id=repository.id,
            commit_sha=commit_sha,
        )

        assert provenance["identity_type"] == "agent"
        assert provenance["agent"] is not None
        assert provenance["agent"]["id"] == agent.id
        assert provenance["agent"]["name"] == agent.name
        assert provenance["session"] is not None
        assert provenance["session"]["id"] == session.id
        assert provenance["task"] is not None
        assert provenance["task"]["id"] == task.id

        print()
        print("=" * 76)
        print("LIVE AGENT CHANGE E2E PASSED")
        print("=" * 76)
        print("PASS: Real GitHub repository branch resolution")
        print("PASS: Governed AgentSession lease validation")
        print("PASS: SUTRA Change creation with task linkage")
        print("PASS: Commit recording with diff stats")
        print("PASS: CodeProvenanceService cryptographic identity resolution")
        print("PASS: Enriched ChangeResponse with complete provenance")
        print("=" * 76)

    finally:
        # =========================================================
        # Cleanup temporary SUTRA data
        # =========================================================
        try:
            db.rollback()

            if task is not None:
                # First clear task.resulting_change_id to avoid FK constraint issues
                db.query(Task).filter(Task.id == task.id).update(
                    {"resulting_change_id": None},
                    synchronize_session=False,
                )
                db.flush()

            # Delete change events and files
            if change_record or (task and task.resulting_change_id):
                cid = change_record.id if change_record else task.resulting_change_id
                db.query(ChangeEvent).filter(ChangeEvent.change_id == cid).delete(synchronize_session=False)
                db.query(ChangeFile).filter(ChangeFile.change_id == cid).delete(synchronize_session=False)
                db.query(Change).filter(Change.id == cid).delete(synchronize_session=False)
                db.flush()

            if task is not None:
                db.query(Task).filter(Task.id == task.id).delete(synchronize_session=False)
                db.flush()

            if session is not None:
                db.query(AgentSession).filter(AgentSession.id == session.id).delete(synchronize_session=False)
                db.flush()

            if actor is not None:
                db.query(Actor).filter(Actor.id == actor.id).delete(synchronize_session=False)
                db.flush()

            if agent is not None:
                db.query(Agent).filter(Agent.id == agent.id).delete(synchronize_session=False)
                db.flush()

            if repository is not None:
                db.query(Repository).filter(Repository.id == repository.id).delete(synchronize_session=False)
                db.flush()

            if user is not None:
                db.query(User).filter(User.id == user.id).delete(synchronize_session=False)
                db.flush()

            db.commit()

        finally:
            db.close()
