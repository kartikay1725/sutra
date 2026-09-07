import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.change import Change
from app.models.actor import Actor
from app.models.repository import Repository


REPOSITORY_ID = "11f57b12-64b7-4e0b-b7a2-9ccfb2ce34ef"


def main():
    with SessionLocal() as db:
        repository = db.get(Repository, REPOSITORY_ID)

        print("REPOSITORY")
        print("=" * 70)

        if not repository:
            print("Repository not found")
            return

        print("name:", repository.name)
        print("provider_type:", repository.provider_type)
        print("provider_owner:", repository.provider_owner)

        changes = db.scalars(
            select(Change)
            .where(Change.repository_id == repository.id)
            .order_by(Change.created_at.desc())
        ).all()

        print()
        print("CHANGES")
        print("=" * 70)

        if not changes:
            print("No Change records found.")
            return

        for change in changes:
            actor = db.get(Actor, change.actor_id)

            print()
            print("change_id:", change.id)
            print("resulting_commit:", change.resulting_commit)
            print("base_commit:", change.base_commit)
            print("status:", change.status)
            print("actor_id:", change.actor_id)

            if actor:
                print("actor_type:", actor.type)
                print("actor_name:", actor.name)
            else:
                print("actor: NOT FOUND")


if __name__ == "__main__":
    main()