from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class InlineReviewComment(Base):
    __tablename__ = "inline_review_comments"

    STATUS_ACTIVE = "active"
    STATUS_RESOLVED = "resolved"
    VALID_STATUSES = {STATUS_ACTIVE, STATUS_RESOLVED}

    SIDE_LEFT = "LEFT"
    SIDE_RIGHT = "RIGHT"
    VALID_SIDES = {SIDE_LEFT, SIDE_RIGHT}

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

    author_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    parent_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("inline_review_comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        index=True,
    )

    diff_side: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    line_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    line_range_start: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    line_range_end: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    commit_sha: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=STATUS_ACTIVE,
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

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    resolved_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'resolved')",
            name="ck_inline_review_comments_status",
        ),
        CheckConstraint(
            "diff_side IS NULL OR diff_side IN ('LEFT', 'RIGHT')",
            name="ck_inline_review_comments_side",
        ),
    )
