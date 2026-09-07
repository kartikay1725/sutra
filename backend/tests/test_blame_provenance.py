import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)

from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.repository import Repository
from app.models.user import User


OWNER_USERNAME = "kartiay1725"
REPOSITORY_SLUG = "dam-project"


def test_github_blame_contains_external_provenance():
    db = SessionLocal()

    try:
        user = db.query(User).filter(
            User.username == OWNER_USERNAME
        ).first()

        assert user is not None, (
            f"SUTRA user '{OWNER_USERNAME}' not found"
        )

        repository = db.query(Repository).filter(
            Repository.owner_id == user.id,
            Repository.slug == REPOSITORY_SLUG,
            Repository.deleted_at.is_(None),
        ).first()

        assert repository is not None, (
            f"Repository '{REPOSITORY_SLUG}' not found"
        )

        with TestClient(app) as client:
            response = client.get(
                f"/v1/repositories/{OWNER_USERNAME}/{REPOSITORY_SLUG}/blame",
                params={
                    "path": "README.md",
                    "ref": "master",
                },
            )

        assert response.status_code == 200, response.text

        data = response.json()

        assert data["repository_id"] == repository.id
        assert data["path"] == "README.md"
        assert data["ref"] == "master"
        assert isinstance(data["ranges"], list)
        assert len(data["ranges"]) > 0

        first_range = data["ranges"][0]

        assert "start_line" in first_range
        assert "end_line" in first_range
        assert "commit" in first_range
        assert "short_commit" in first_range
        assert "author_name" in first_range
        assert "provenance" in first_range

        provenance = first_range["provenance"]

        assert provenance["source"] == "github"
        assert provenance["tracked"] is False
        assert provenance["identity_type"] == "external"

        assert provenance["actor_id"] is None
        assert provenance["actor_name"] is None
        assert provenance["change_id"] is None
        assert provenance["agent"] is None
        assert provenance["session"] is None
        assert provenance["task"] is None

    finally:
        db.close()


if __name__ == "__main__":
    test_github_blame_contains_external_provenance()
    print("PASS: GitHub blame API returns external provenance.")