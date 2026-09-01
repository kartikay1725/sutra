from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in type(dbapi_connection).__module__:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class Base(DeclarativeBase):
    pass


engine_kwargs = {
    "pool_pre_ping": True,
}

# Production pooling for non-SQLite databases.
if (
    settings.app_env.lower() == "production"
    and "sqlite" not in settings.database_url.lower()
):
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
    engine_kwargs["pool_timeout"] = 30


engine = create_engine(
    settings.database_url,
    **engine_kwargs,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI database dependency.

    A new SQLAlchemy session is created for each request and always closed
    after the request finishes.
    """
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()