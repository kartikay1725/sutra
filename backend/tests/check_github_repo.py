import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.repository import Repository
from app.models.user import User


USERNAME = "kartikay1725"


def main():
    with SessionLocal() as db:
        user = db.scalar(
            select(User).where(
                User.username == USERNAME
            )
        )

        print("USER")
        print("=" * 60)

        if not user:
            print("NOT FOUND:", USERNAME)
            return

        print("id:", user.id)
        print("username:", user.username)

        repos = db.scalars(
            select(Repository).where(
                Repository.owner_id == user.id
            )
        ).all()

        print()
        print("REPOSITORIES")
        print("=" * 60)

        if not repos:
            print("No repositories found.")
            return

        for repo in repos:
            print()
            print("id:", repo.id)
            print("slug:", repo.slug)
            print("name:", repo.name)
            print("provider_type:", repo.provider_type)
            print("provider_owner:", repo.provider_owner)
            print("external_id:", repo.external_id)
            print("default_branch:", repo.default_branch)


if __name__ == "__main__":
    main()