from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Change(Base):
    __tablename__ = "changes"

    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed', 'recorded', 'blocked', 'rejected')",
            name="ck_changes_status",
        ),
        UniqueConstraint(
            "operation_key",
            name="uq_changes_operation_key",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    repository_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "repositories.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    actor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "actors.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    intent: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    base_commit: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    resulting_commit: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    # ---------------------------------------------------------
    # IDEMPOTENCY
    #
    # SHA-256 fingerprint of the canonical Git operation:
    #
    # repository + actor + ref + before commit + after commit
    #
    # This is intentionally separate from the UUID primary key.
    # The database uniqueness constraint is the authoritative
    # concurrency boundary.
    # ---------------------------------------------------------

    operation_key: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="proposed",
        nullable=False,
        index=True,
    )

    risk_level: Mapped[str] = mapped_column(
        String(20),
        default="unknown",
        nullable=False,
    )

    metadata_json: Mapped[str] = mapped_column(
        Text,
        default="{}",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )