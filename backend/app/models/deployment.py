from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Deployment(Base):
    __tablename__ = "deployments"

    STATUS_QUEUED = "queued"
    STATUS_DEPLOYING = "deploying"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_ROLLED_BACK = "rolled_back"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    environment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    repository_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    commit_sha: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    change_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("changes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    actor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("actors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=STATUS_QUEUED,
        index=True,
    )

    log_output: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'deploying', 'success', 'failed', 'rolled_back')",
            name="ck_deployments_status",
        ),
    )
