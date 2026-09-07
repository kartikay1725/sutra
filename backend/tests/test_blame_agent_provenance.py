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
from app.models.user import User
from app.models.repository import Repository
from app.models.agent import Agent
from app.models.actor import Actor
from app.models.agent_session import AgentSession
from app.models.task import Task
from app.models.change import Change
from app.core.security import hash_password
import app.api.repository_browser as repository_browser_api


OWNER_USERNAME = "kartikay1725"
REPOSITORY_SLUG = "dam-project"


def test_blame_api_returns_sutra_agent_provenance(monkeypatch):
    db = SessionLocal()

    user = None
    agent = None
    actor = None
    session = None
    task = None
    change = None

    # -------------------------------------------------------------
    # IMPORTANT:
    # Generate ONE unique fake SHA for this test run.
    # Every part of the test uses this exact same value:
    #
    # Fake GitHub blame
    #        ↓
    # Change.resulting_commit
    #        ↓
    # CodeProvenanceService
    #        ↓
    # Agent provenance
    # -------------------------------------------------------------
    fake_commit_sha = uuid4().hex + uuid4().hex

    class FakeGitHubProvider:
        """
        Test-only GitHub provider.

        It simulates GitHub returning a blame range whose
        commit SHA is tracked by a SUTRA Change.
        """

        def get_file_blame(
            self,
            owner: str,
            name: str,
            path: str,
            ref: str,
        ):
            assert owner == "kartikay1725"
            assert name == REPOSITORY_SLUG
            assert path == "README.md"
            assert ref == "master"

            return [
                {
                    "start_line": 1,
                    "end_line": 1,
                    "age": 1,
                    "commit": fake_commit_sha,
                    "short_commit": fake_commit_sha[:7],
                    "subject": "Agent-created test commit",
                    "author_name": "Blame API Test Agent",
                    "author_email": "agent@test.local",
                    "github_login": None,
                    "authored_at": None,
                }
            ]

    try:
        # ---------------------------------------------------------
        # Locate an existing real GitHub-backed SUTRA repository.
        # ---------------------------------------------------------
        user = db.scalar(
            select(User).where(
                User.username == OWNER_USERNAME
            )
        )

        assert user is not None, (
            f"SUTRA user '{OWNER_USERNAME}' not found"
        )

        repository = db.scalar(
            select(Repository).where(
                Repository.owner_id == user.id,
                Repository.slug == REPOSITORY_SLUG,
                Repository.deleted_at.is_(None),
            )
        )

        assert repository is not None, (
            f"SUTRA repository '{REPOSITORY_SLUG}' not found"
        )

        # ---------------------------------------------------------
        # Create temporary agent.
        # ---------------------------------------------------------
        agent = Agent(
            id=str(uuid4()),
            owner_id=user.id,
            name="Blame API Test Agent",
            description="Temporary API provenance test agent",
            provider="test",
            model="test-model",
            token_hash=hash_password(
                f"agent-token-{uuid4().hex}"
            ),
            token_prefix=uuid4().hex[:16],
            status="active",
            is_active=True,
        )

        db.add(agent)
        db.flush()

        # ---------------------------------------------------------
        # Agent identity / actor.
        # ---------------------------------------------------------
        actor = Actor(
            id=agent.id,
            type="agent",
            name=agent.name,
            owner_id=user.id,
            capabilities=(
                '["repository.read",'
                '"repository.write",'
                '"change.create",'
                '"change.commit"]'
            ),
        )

        db.add(actor)
        db.flush()

        # ---------------------------------------------------------
        # Create temporary AgentSession.
        # ---------------------------------------------------------
        session = AgentSession(
            id=str(uuid4()),
            agent_id=agent.id,
            token_hash=hash_password(
                f"session-token-{uuid4().hex}"
            ),
            token_prefix=uuid4().hex[:32],
            status="active",
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(hours=1)
            ),
            last_seen_at=datetime.now(timezone.utc),
        )

        db.add(session)
        db.flush()

        # ---------------------------------------------------------
        # Create temporary Change.
        #
        # MUST use the exact same fake SHA returned by the fake
        # GitHub provider.
        # ---------------------------------------------------------
        change = Change(
            id=str(uuid4()),
            repository_id=repository.id,
            actor_id=actor.id,
            intent="Test line-level agent provenance",
            base_commit=None,
            resulting_commit=fake_commit_sha,
            operation_key=f"blame-api-test-{uuid4().hex}",
            status="recorded",
            risk_level="low",
            metadata_json="{}",
        )

        db.add(change)
        db.flush()

        # ---------------------------------------------------------
        # Create Task linking:
        #
        # Task → Agent
        # Task → AgentSession
        # Task → Change
        # ---------------------------------------------------------
        task = Task(
            id=str(uuid4()),
            repository_id=repository.id,
            created_by=user.id,
            assigned_agent_id=agent.id,
            assigned_user_id=None,
            claimed_by_session_id=session.id,
            lease_expires_at=(
                datetime.now(timezone.utc)
                + timedelta(hours=1)
            ),
            resulting_change_id=change.id,
            resulting_pull_request_id=None,
            title="Blame API Agent Provenance Test",
            description="Test line-level agent provenance",
            status=Task.STATUS_IN_PROGRESS,
            priority=Task.PRIORITY_MEDIUM,
            priority_index=0.0,
            task_type=Task.TYPE_FEATURE,
            source="test",
        )

        db.add(task)

        # Commit so the FastAPI TestClient's DB session can see the
        # fixture records.
        db.commit()

        # ---------------------------------------------------------
        # Replace only the provider construction.
        #
        # The real endpoint and CodeProvenanceService remain under
        # test.
        # ---------------------------------------------------------
        monkeypatch.setattr(
            repository_browser_api,
            "_github_provider",
            lambda repository: FakeGitHubProvider(),
        )

        with TestClient(app) as client:
            response = client.get(
                f"/v1/repositories/"
                f"{OWNER_USERNAME}/{REPOSITORY_SLUG}/blame",
                params={
                    "path": "README.md",
                    "ref": "master",
                },
            )

        # ---------------------------------------------------------
        # API assertions.
        # ---------------------------------------------------------
        assert response.status_code == 200, response.text

        data = response.json()

        assert data["repository_id"] == repository.id
        assert data["path"] == "README.md"
        assert data["ref"] == "master"

        assert len(data["ranges"]) == 1

        blame_range = data["ranges"][0]

        assert blame_range["commit"] == fake_commit_sha
        assert blame_range["short_commit"] == fake_commit_sha[:7]

        # ---------------------------------------------------------
        # IMPORTANT PROVENANCE ASSERTIONS
        # ---------------------------------------------------------
        provenance = blame_range["provenance"]

        assert provenance["source"] == "sutra"
        assert provenance["tracked"] is True
        assert provenance["identity_type"] == "agent"

        # Actor
        assert provenance["actor_id"] == agent.id
        assert provenance["actor_name"] == agent.name

        # Change
        assert provenance["change_id"] == change.id

        # Agent
        assert provenance["agent"] is not None
        assert provenance["agent"]["id"] == agent.id
        assert provenance["agent"]["name"] == agent.name
        assert provenance["agent"]["provider"] == "test"
        assert provenance["agent"]["model"] == "test-model"

        # Session
        assert provenance["session"] is not None
        assert provenance["session"]["id"] == session.id
        assert provenance["session"]["status"] == "active"

        # Task
        assert provenance["task"] is not None
        assert provenance["task"]["id"] == task.id
        assert (
            provenance["task"]["title"]
            == "Blame API Agent Provenance Test"
        )
        assert (
            provenance["task"]["status"]
            == Task.STATUS_IN_PROGRESS
        )
        assert (
            provenance["task"]["task_type"]
            == Task.TYPE_FEATURE
        )

        print(
            "PASS: Blame API → Change → Agent provenance works."
        )
        print(
            "PASS: Blame API → Agent → Session → Task "
            "provenance works."
        )

    finally:
        # ---------------------------------------------------------
        # CLEANUP
        #
        # Delete in dependency order and flush after each level.
        # ---------------------------------------------------------
        db.rollback()

        # 1. Task
        if task is not None:
            db.query(Task).filter(
                Task.id == task.id
            ).delete(synchronize_session=False)

        db.flush()

        # 2. Change
        if change is not None:
            db.query(Change).filter(
                Change.id == change.id
            ).delete(synchronize_session=False)

        db.flush()

        # 3. AgentSession
        if session is not None:
            db.query(AgentSession).filter(
                AgentSession.id == session.id
            ).delete(synchronize_session=False)

        db.flush()

        # 4. Actor
        if actor is not None:
            db.query(Actor).filter(
                Actor.id == actor.id
            ).delete(synchronize_session=False)

        db.flush()

        # 5. Agent
        if agent is not None:
            db.query(Agent).filter(
                Agent.id == agent.id
            ).delete(synchronize_session=False)

        db.commit()
        db.close()