from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Repository(Base):
    # Partial unique index enforced at migration level:
    # CREATE UNIQUE INDEX uq_repo_provider_external ON repositories (provider_type, external_id)
    # WHERE external_id IS NOT NULL;
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    owner_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("actors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    visibility: Mapped[str] = mapped_column(
        String(20),
        default="private",
        nullable=False,
    )

    default_branch: Mapped[str] = mapped_column(
        String(255),
        default="main",
        nullable=False,
    )

    storage_key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    # ---------------------------------------------------------------------------
    # Provider identity — added for GitHub repository sync
    # For local repos: provider_type="local", external_id=None
    # For GitHub repos: provider_type="github", external_id=str(github_repo_id)
    # ---------------------------------------------------------------------------
    provider_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="local",
        server_default="local",
    )

    external_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    # The numeric GitHub installation ID that gives access to this repository.
    # Nullable — only set for provider_type="github".
    github_installation_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
    )

    # The GitHub owner login (username or org name) for this repository.
    provider_owner: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    settings: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
    )

    github_objects_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
