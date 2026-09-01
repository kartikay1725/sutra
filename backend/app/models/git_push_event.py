from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class GitPushEvent(Base):
    __tablename__ = "git_push_events"

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_PROCESSED = "processed"
    STATUS_FAILED = "failed"
    STATUS_DEAD_LETTER = "dead_letter"

    __table_args__ = (
    CheckConstraint(
        "status IN ('pending', 'processing', 'processed', 'failed', 'dead_letter')",
        name="ck_git_push_events_status",
    ),
    CheckConstraint(
        "attempts >= 0",
        name="ck_git_push_events_attempts_nonnegative",
    ),

    CheckConstraint(
        """
        (
            status = 'processed'
            AND processed_at IS NOT NULL
        )
        OR
        (
            status != 'processed'
            AND processed_at IS NULL
        )
        """,
        name="ck_git_push_events_processed_at_consistency",
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

    before_refs_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
    )

    after_refs_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
    )

    # ---------------------------------------------------------
    # INTEGRITY
    # ---------------------------------------------------------
    #
    # Version 2 = HMAC-SHA256.
    #
    # The secret used to generate/verify integrity_hash is
    # stored outside the database in EVENT_INTEGRITY_KEY.
    # ---------------------------------------------------------

    integrity_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
    )

    integrity_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        index=True,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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
    worker_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )