from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AgentRegistrationRequest(Base):
    __tablename__ = "agent_registration_requests"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    agent_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    agent_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    provider: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    model: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    requested_for_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    requested_capabilities: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )

    requested_repo_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    new_repo: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )

    temporary_token: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    temporary_token_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_temporary_token_used: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        index=True,
    )

    polling_token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    permanent_token_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    approved_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
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

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    approved_by_user = relationship(
        "User",
        foreign_keys=[approved_by_user_id],
    )
