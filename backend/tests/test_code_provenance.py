import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.services.code_provenance_service import CodeProvenanceService


REPOSITORY_ID = "11f57b12-64b7-4e0b-b7a2-9ccfb2ce34ef"

# Real historical GitHub commit from README.md
EXTERNAL_COMMIT = "fbd86d87cf533be4da438d95165c56ddd3e40ffd"


def main():
    with SessionLocal() as db:
        service = CodeProvenanceService(db)

        print("Testing external GitHub commit")
        print("=" * 70)

        result = service.resolve_commit(
            repository_id=REPOSITORY_ID,
            commit_sha=EXTERNAL_COMMIT,
        )

        print(result)

        assert result["source"] == "github"
        assert result["tracked"] is False
        assert result["identity_type"] == "external"

        print()
        print("PASS: Historical GitHub commit is correctly marked external.")

        print()
        print("Testing empty/unknown commit")
        print("=" * 70)

        unknown = service.resolve_commit(
            repository_id=REPOSITORY_ID,
            commit_sha="0000000000000000000000000000000000000000",
        )

        print(unknown)

        assert unknown["source"] == "github"
        assert unknown["tracked"] is False
        assert unknown["identity_type"] == "external"

        print()
        print("PASS: Unknown commit is correctly marked external.")


if __name__ == "__main__":
    main()