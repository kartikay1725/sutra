import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.models.actor import Actor
from app.models.change import Change
from app.services.code_provenance_service import CodeProvenanceService


REPOSITORY_ID = "11f57b12-64b7-4e0b-b7a2-9ccfb2ce34ef"


def main():
    with SessionLocal() as db:
        # ---------------------------------------------------------
        # Create temporary SUTRA Human Actor
        # ---------------------------------------------------------
        human_actor = Actor(
            id=str(uuid4()),
            type="human",
            name="Provenance Test Human",
            owner_id=None,
            capabilities="[]",
        )

        db.add(human_actor)
        db.flush()

        # ---------------------------------------------------------
        # Create temporary Change pointing to a fake commit SHA
        # ---------------------------------------------------------
        commit_sha = "a" * 40

        change = Change(
            id=str(uuid4()),
            repository_id=REPOSITORY_ID,
            actor_id=human_actor.id,
            intent="Provenance unit test",
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
        # Resolve provenance
        # ---------------------------------------------------------
        service = CodeProvenanceService(db)

        result = service.resolve_commit(
            repository_id=REPOSITORY_ID,
            commit_sha=commit_sha,
        )

        print("SUTRA TRACKED HUMAN COMMIT")
        print("=" * 70)
        print(result)

        # ---------------------------------------------------------
        # Assertions
        # ---------------------------------------------------------
        assert result["source"] == "sutra"
        assert result["tracked"] is True
        assert result["identity_type"] == "human"
        assert result["actor_id"] == human_actor.id
        assert result["actor_name"] == "Provenance Test Human"
        assert result["change_id"] == change.id
        assert result["agent"] is None
        assert result["session"] is None
        assert result["task"] is None

        print()
        print("PASS: SUTRA Change → Actor → Human provenance works.")

        # ---------------------------------------------------------
        # IMPORTANT:
        # Roll back the test data so the real database stays clean.
        # ---------------------------------------------------------
        db.rollback()

        print("PASS: Test transaction rolled back; database unchanged.")


if __name__ == "__main__":
    main()