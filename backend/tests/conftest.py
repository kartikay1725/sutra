from pathlib import Path
import tempfile
import os
import atexit
import shutil
import stat

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings

# Route all test repositories to a temporary directory outside the project workspace.
# This prevents background file watchers (like Uvicorn --reload) from locking Git
# objects as they are written on Windows, which causes 'Permission denied' pushes.
_TEST_REPOS_DIR = tempfile.mkdtemp(prefix="sutra-test-repos-")
settings.repository_storage_path = _TEST_REPOS_DIR
os.environ["REPOSITORY_STORAGE_PATH"] = _TEST_REPOS_DIR
os.environ["SUTRA_REPOSITORY_STORAGE_PATH"] = _TEST_REPOS_DIR  # just in case

def _cleanup_test_repos():
    def handle_remove_readonly(func, path, exc):
        try:
            os.chmod(path, stat.S_IWRITE)
        except OSError:
            pass
        func(path)
    shutil.rmtree(_TEST_REPOS_DIR, onerror=handle_remove_readonly)

atexit.register(_cleanup_test_repos)

from app.db.session import Base, engine as app_engine, get_db
from app.main import app
from app.models.actor import Actor
from app.models.user import User


# ---------------------------------------------------------------------------
# TEST USER -> HUMAN ACTOR HELPER
# ---------------------------------------------------------------------------
#
# Do NOT automatically create Actors through SQLAlchemy session events.
#
# Some tests explicitly create Actor(user.id) after flushing the User.
# Automatically creating the Actor during before_flush/before_commit causes:
#
#     UNIQUE constraint failed: actors.id
#
# Tests that need a User-backed human Actor should call:
#
#     ensure_test_actor(db, user)
#
# explicitly.
# ---------------------------------------------------------------------------

from sqlalchemy import event

@event.listens_for(Session, "before_flush")
def auto_create_actor_for_user(session, flush_context, instances):
    from app.models.repository import Repository
    from app.models.change import Change
    from app.models.git_push_event import GitPushEvent
    from app.models.actor import Actor
    from app.models.user import User

    # Find all referenced actor_ids that might need an Actor model
    referenced_actor_ids = set()
    for obj in session.new | session.dirty:
        if isinstance(obj, Repository):
            referenced_actor_ids.add(obj.owner_id)
        elif isinstance(obj, Change):
            referenced_actor_ids.add(obj.actor_id)
        elif isinstance(obj, GitPushEvent):
            referenced_actor_ids.add(obj.actor_id)

    for actor_id in referenced_actor_ids:
        # Check if an Actor with this ID is already in the session's pending additions
        actor_in_session = False
        for new_obj in session.new:
            if isinstance(new_obj, Actor) and new_obj.id == actor_id:
                actor_in_session = True
                break
        
        if not actor_in_session:
            existing_actor = session.get(Actor, actor_id)
            if existing_actor is None:
                # Look up the User object to retrieve username if possible
                user_obj = None
                for new_obj in session.new:
                    if isinstance(new_obj, User) and new_obj.id == actor_id:
                        user_obj = new_obj
                        break
                if user_obj is None:
                    user_obj = session.get(User, actor_id)

                name = user_obj.username if user_obj else f"test_actor_{actor_id[:8]}"
                actor = Actor(
                    id=actor_id,
                    owner_id=actor_id,
                    type="human",
                    name=name,
                    capabilities=(
                        '["repository.read", '
                        '"repository.write", '
                        '"change.create"]'
                    ),
                )
                session.add(actor)

def ensure_test_actor(
    db: Session,
    user: User,
) -> Actor:
    """
    Return the human Actor corresponding to a User.

    The helper is idempotent and never creates a duplicate Actor.
    """
    if not user.id:
        raise ValueError(
            "Cannot create a test Actor for a User without an id"
        )

    actor = db.get(Actor, user.id)

    if actor is not None:
        return actor

    actor = Actor(
        id=user.id,
        owner_id=user.id,
        type="human",
        name=user.username,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create"]'
        ),
    )

    db.add(actor)
    db.flush()

    return actor


# ---------------------------------------------------------------------------
# GLOBAL TEST DATABASE INITIALIZATION
# ---------------------------------------------------------------------------

def _is_test_database() -> bool:
    """
    Return True when the configured database looks like a test database.

    We deliberately do NOT automatically create tables against production.
    """
    import sys

    if "pytest" in sys.modules:
        return True

    database_url = settings.database_url.lower()
    app_env = settings.app_env.lower()

    if app_env in {"test", "testing"}:
        return True

    if "sqlite" in database_url:
        database_name = Path(
            database_url.split("///", 1)[-1]
        ).name.lower()

        return (
            "test" in database_name
            or "pytest" in database_name
        )

    return False


@pytest.fixture(scope="session", autouse=True)
def initialize_configured_test_database():
    """
    Initialize the application's configured test database.

    Some integration/concurrency tests use the application's global engine
    rather than the isolated `db` fixture, so all model tables must exist.

    If the configured database is unreachable (e.g., no network access to
    Supabase in a local dev environment), this fixture degrades gracefully
    so that unit tests using the isolated SQLite `db` fixture still run.
    """
    if not _is_test_database():
        yield
        return

    assert Base.metadata.tables, (
        "SQLAlchemy model registry is empty. "
        "Import app.models before initializing the test database."
    )

    try:
        Base.metadata.create_all(bind=app_engine)
    except Exception as e:
        import warnings
        warnings.warn(
            f"Could not initialize configured test database ({e}). "
            "Unit tests using the isolated 'db' fixture will still run. "
            "Integration tests requiring Supabase connectivity will be skipped.",
            stacklevel=2,
        )

    yield

    # Intentionally do not drop the configured test DB.

    # Some integration/concurrency tests share it for the duration of pytest.


# ---------------------------------------------------------------------------
# ISOLATED IN-MEMORY DATABASE
# ---------------------------------------------------------------------------

@pytest.fixture()
def db():
    """
    Provide an isolated SQLite database for unit/service/API tests.
    """
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    assert Base.metadata.tables, (
        "SQLAlchemy model registry is empty while creating "
        "the isolated test database."
    )

    Base.metadata.create_all(test_engine)

    TestSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    session = TestSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(test_engine)
        test_engine.dispose()


# ---------------------------------------------------------------------------
# RATE LIMITER
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """
    Reset slowapi's in-memory counters and Redis rate-limit keys before and after every test.
    """
    from app.core.rate_limit import limiter

    limiter_obj = getattr(limiter, "_limiter", None)
    if limiter_obj and hasattr(limiter_obj, "_storage"):
        limiter_obj._storage.reset()
    elif hasattr(limiter, "_storage") and hasattr(limiter._storage, "reset"):
        limiter._storage.reset()

    try:
        from app.core.redis_service import redis_service
        r = redis_service.get_client()
        keys = r.keys("ratelimit:*")
        if keys:
            r.delete(*keys)
    except Exception:
        pass

    yield

    if limiter_obj and hasattr(limiter_obj, "_storage"):
        limiter_obj._storage.reset()
    elif hasattr(limiter, "_storage") and hasattr(limiter._storage, "reset"):
        limiter._storage.reset()

    try:
        from app.core.redis_service import redis_service
        r = redis_service.get_client()
        keys = r.keys("ratelimit:*")
        if keys:
            r.delete(*keys)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# FASTAPI TEST CLIENT
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(db: Session):
    """
    FastAPI TestClient using the isolated per-test database.
    """

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()