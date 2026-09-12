from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    Float,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Task(Base):
    __tablename__ = "tasks"

    STATUS_OPEN = "open"
    STATUS_ASSIGNED = "assigned"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_BLOCKED = "blocked"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    PRIORITY_LOW = "low"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_HIGH = "high"
    PRIORITY_CRITICAL = "critical"

    TYPE_FEATURE = "feature"
    TYPE_BUGFIX = "bugfix"
    TYPE_REFACTOR = "refactor"
    TYPE_SECURITY = "security"
    TYPE_DOCUMENTATION = "documentation"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    repository_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    assigned_agent_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    assigned_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    claimed_by_session_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "agent_sessions.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    resulting_change_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("changes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    resulting_pull_request_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("pull_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=STATUS_OPEN,
        index=True,
    )

    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PRIORITY_MEDIUM,
    )

    priority_index: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        index=True,
    )

    task_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=TYPE_FEATURE,
    )

    source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="user",
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

    execution_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    validation_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN "
            "('open', 'assigned', 'in_progress', "
            "'blocked', 'completed', 'cancelled')",
            name="ck_tasks_status",
        ),
        CheckConstraint(
            "priority IN "
            "('low', 'medium', 'high', 'critical')",
            name="ck_tasks_priority",
        ),
        CheckConstraint(
            "task_type IN "
            "('feature', 'bugfix', 'refactor', "
            "'security', 'documentation')",
            name="ck_tasks_type",
        ),
    )