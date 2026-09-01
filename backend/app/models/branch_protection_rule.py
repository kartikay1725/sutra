from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class BranchProtectionRule(Base):
    __tablename__ = "branch_protection_rules"

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

    branch_pattern: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    required_approvals: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    require_change_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    require_clean_conflict: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    require_resolved_threads: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    require_agent_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    require_no_blocking_agent_findings: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    allow_author_self_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    require_ci_passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    updated_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
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
        UniqueConstraint(
            "repository_id",
            "branch_pattern",
            name="uq_branch_protection_repo_pattern",
        ),
        CheckConstraint(
            "required_approvals >= 0",
            name="ck_branch_protection_req_approvals",
        ),
    )
