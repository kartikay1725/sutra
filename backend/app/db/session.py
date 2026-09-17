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

# Supabase session-mode / transaction-mode pooling has a small connection ceiling
# and multiplexes connections through PgBouncer. Disabling prepared statements
# via prepare_threshold=None prevents DuplicatePreparedStatement errors.
if "sqlite" not in settings.database_url.lower():
    engine_kwargs.update(
        connect_args={"prepare_threshold": None},
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout_seconds,
        pool_recycle=settings.database_pool_recycle_seconds,
        pool_use_lifo=True,
    )


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