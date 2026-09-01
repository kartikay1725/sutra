from app.db.session import Base, engine
from app.models import (
    Actor,
    Agent,
    Change,
    ChangeDependency,
    ChangeEvent,
    ChangeFile,
    ChangeReview,
    GitPushEvent,
    Repository,
    User,
)


from app.core.config import settings

def main() -> None:
    if settings.app_env.lower() == "production":
        raise RuntimeError(
            "init_db.py must not be used in production. "
            "Use Alembic migrations instead."
        )
    # Importing all models above registers their tables
    # with SQLAlchemy metadata before create_all().
    Base.metadata.create_all(bind=engine)

    print("SUTRA database initialized.")


if __name__ == "__main__":
    main()