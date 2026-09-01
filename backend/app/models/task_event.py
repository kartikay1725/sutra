from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class TaskEvent(Base):
    """
    Immutable lifecycle/audit event for a Task.

    TaskEvent is intentionally separate from ChangeEvent.

    ChangeEvent belongs to the Change lifecycle.
    TaskEvent belongs to the Task lifecycle.
    """

    __tablename__ = "task_events"

    EVENT_CREATED = "task.created"
    EVENT_ASSIGNED = "task.assigned"
    EVENT_STARTED = "task.started"
    EVENT_CLAIMED = "task.claimed"
    EVENT_HEARTBEAT = "task.heartbeat"
    EVENT_LEASE_EXPIRED = "task.lease_expired"
    EVENT_RELEASED = "task.released"
    EVENT_BLOCKED = "task.blocked"
    EVENT_CHANGE_CREATED = "task.change_created"
    EVENT_PULL_REQUEST_CREATED = "task.pull_request_created"
    EVENT_COMPLETED = "task.completed"
    EVENT_CANCELLED = "task.cancelled"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "tasks.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # Actor ID is intentionally not a database FK.
    #
    # Existing SUTRA actor compatibility allows both:
    # - human/user actor IDs
    # - agent actor IDs
    #
    # Keeping this loosely coupled prevents historical events
    # from becoming invalid when an actor is removed or migrated.
    actor_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    # The agent session that performed the operation, when applicable.
    #
    # Session deletion/revocation must never destroy historical events.
    session_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "agent_sessions.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    from_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    to_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    metadata_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
