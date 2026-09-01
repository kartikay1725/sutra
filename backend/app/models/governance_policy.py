from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from app.db.session import Base


class GovernancePolicy(Base):
    __tablename__ = "governance_policies"

    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    enforce_branch_protection = Column(Boolean, nullable=False, default=True)
    minimum_pr_approvals = Column(Integer, nullable=False, default=1)
    restrict_public_repositories = Column(Boolean, nullable=False, default=False)
    require_signed_commits = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
