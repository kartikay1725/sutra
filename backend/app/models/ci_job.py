from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CIJob(Base):
    __tablename__ = "ci_jobs"

    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_PASSED = "passed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_TIMED_OUT = "timed_out"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    pull_request_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pull_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    repository_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    change_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("changes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    commit_sha: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    target_branch: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=STATUS_QUEUED,
        index=True,
    )

    trigger: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pull_request",
    )

    runner_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="isolated_process",
    )

    exit_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    output_log: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
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

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'passed', 'failed', 'cancelled', 'timed_out')",
            name="ck_ci_jobs_status",
        ),
    )
