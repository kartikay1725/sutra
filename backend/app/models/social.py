from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, PrimaryKeyConstraint
from app.db.session import Base

class RepositoryStar(Base):
    __tablename__ = "repository_stars"

    actor_id = Column(String(36), ForeignKey("actors.id", ondelete="CASCADE"), index=True, nullable=False)
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("actor_id", "repository_id"),
    )


class ActorFollow(Base):
    __tablename__ = "actor_follows"

    follower_id = Column(String(36), ForeignKey("actors.id", ondelete="CASCADE"), index=True, nullable=False)
    following_id = Column(String(36), ForeignKey("actors.id", ondelete="CASCADE"), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("follower_id", "following_id"),
    )
