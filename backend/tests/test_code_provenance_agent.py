import sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.change import Change
from app.models.task import Task
from app.services.code_provenance_service import CodeProvenanceService


REPOSITORY_ID = "11f57b12-64b7-4e0b-b7a2-9ccfb2ce34ef"
OWNER_ID = "a33555b3-8590-4d99-9dc6-e4bfebd75f29"


def main():
    with SessionLocal() as db:
        try:
            # ---------------------------------------------------------
            # Temporary Agent
            # ---------------------------------------------------------
            agent_id = str(uuid4())

            agent = Agent(
                id=agent_id,
                owner_id=OWNER_ID,
                name="Provenance Test Agent",
                description="Temporary provenance test agent",
                provider="test",
                model="test-model",
                token_hash="test-token-hash",
                token_prefix=f"test-{uuid4().hex[:8]}",
                status="active",
                is_active=True,
            )

            db.add(agent)
            db.flush()

            # ---------------------------------------------------------
            # Agent Actor
            # ---------------------------------------------------------
            actor = Actor(
                id=agent.id,
                type="agent",
                name=agent.name,
                owner_id=OWNER_ID,
                capabilities='["repository.read","repository.write"]',
            )

            db.add(actor)
            db.flush()

            # ---------------------------------------------------------
            # AgentSession
            # ---------------------------------------------------------
            now = datetime.now(timezone.utc)

            session = AgentSession(
                id=str(uuid4()),
                agent_id=agent.id,
                token_hash="test-session-token-hash",
                token_prefix=f"session-{uuid4().hex[:8]}",
                status="active",
                created_at=now,
                expires_at=now + timedelta(minutes=15),
                last_seen_at=now,
            )

            db.add(session)
            db.flush()

            # ---------------------------------------------------------
            # Change
            # ---------------------------------------------------------
            commit_sha = "b" * 40

            change = Change(
                id=str(uuid4()),
                repository_id=REPOSITORY_ID,
                actor_id=actor.id,
                intent="Agent provenance unit test",
                base_commit=None,
                resulting_commit=commit_sha,
                operation_key=uuid4().hex,
                status="recorded",
                risk_level="low",
                metadata_json="{}",
            )

            db.add(change)
            db.flush()

            # ---------------------------------------------------------
            # Task
            # ---------------------------------------------------------
            task = Task(
                id=str(uuid4()),
                repository_id=REPOSITORY_ID,
                created_by=OWNER_ID,
                assigned_agent_id=agent.id,
                assigned_user_id=None,
                claimed_by_session_id=session.id,
                lease_expires_at=now + timedelta(minutes=10),
                resulting_change_id=change.id,
                resulting_pull_request_id=None,
                title="Provenance Agent Test Task",
                description="Temporary task for provenance testing",
                status=Task.STATUS_IN_PROGRESS,
                priority=Task.PRIORITY_MEDIUM,
                priority_index=0.0,
                task_type=Task.TYPE_FEATURE,
                source="user",
            )

            db.add(task)
            db.flush()

            # ---------------------------------------------------------
            # Resolve provenance
            # ---------------------------------------------------------
            service = CodeProvenanceService(db)

            result = service.resolve_commit(
                repository_id=REPOSITORY_ID,
                commit_sha=commit_sha,
            )

            print("SUTRA TRACKED AGENT COMMIT")
            print("=" * 70)
            print(result)

            # ---------------------------------------------------------
            # Assertions
            # ---------------------------------------------------------
            assert result["source"] == "sutra"
            assert result["tracked"] is True
            assert result["identity_type"] == "agent"

            assert result["actor_id"] == actor.id
            assert result["actor_name"] == agent.name

            assert result["change_id"] == change.id

            assert result["agent"] is not None
            assert result["agent"]["id"] == agent.id
            assert result["agent"]["name"] == agent.name

            assert result["session"] is not None
            assert result["session"]["id"] == session.id

            assert result["task"] is not None
            assert result["task"]["id"] == task.id
            assert result["task"]["title"] == task.title

            print()
            print(
                "PASS: "
                "SUTRA Change → Agent → Session → Task provenance works."
            )

        finally:
            # Roll back everything created by this test.
            db.rollback()

            print(
                "PASS: "
                "Test transaction rolled back; database unchanged."
            )


if __name__ == "__main__":
    main()