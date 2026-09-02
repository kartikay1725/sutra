from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class GitHubInstallation(Base):
    """
    Records the association between a SUTRA user and a GitHub App installation.

    One SUTRA user may have exactly one active GitHub installation record.
    The github_installation_id is the GitHub-side numeric installation ID
    and is globally unique across all SUTRA users.

    IMPORTANT: No installation access tokens are stored here.
    Tokens are fetched on-demand and never persisted.
    """

    __tablename__ = "github_installations"

    __table_args__ = (
        UniqueConstraint("github_installation_id", name="uq_github_installation_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Numeric GitHub installation ID (assigned by GitHub)
    github_installation_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    # GitHub account (user or org) that owns the installation
    github_account_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    github_account_login: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # "User" or "Organization"
    target_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="User",
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
