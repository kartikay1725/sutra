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


class PullRequest(Base):
    __tablename__ = "pull_requests"

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'open', 'approved', 'merged', 'closed', 'rejected')",
            name="ck_pull_requests_status",
        ),
        UniqueConstraint(
            "source_change_id",
            name="uq_pull_requests_source_change_id",
        ),
    )

    STATUS_DRAFT = "draft"
    STATUS_OPEN = "open"
    STATUS_APPROVED = "approved"
    STATUS_MERGED = "merged"
    STATUS_CLOSED = "closed"
    STATUS_REJECTED = "rejected"

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

    author_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("actors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    source_change_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("changes.id", ondelete="CASCADE"),
        nullable=False,
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

    target_branch: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    source_commit: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    target_commit: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default=STATUS_OPEN,
        nullable=False,
        index=True,
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

    merged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
