import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.user import User


def main():
    with SessionLocal() as db:
        users = db.scalars(
            select(User)
        ).all()

        print("SUTRA USERS")
        print("=" * 70)

        if not users:
            print("NO USERS FOUND")
            return

        for user in users:
            print()
            print("id:", user.id)
            print("username:", user.username)
            print("email:", user.email)


if __name__ == "__main__":
    main()