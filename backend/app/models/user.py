from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from sqlalchemy import Boolean, DateTime, Integer, JSON, String


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    username: Mapped[str] = mapped_column(
        String(39),
        unique=True,
        index=True,
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(320),
        unique=True,
        index=True,
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    email_otp_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    email_otp_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    email_otp_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    email_otp_last_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    password_reset_token_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    password_reset_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    password_reset_last_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    bio: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    social_links: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    agents = relationship(
        "Agent",
        back_populates="owner",
        cascade="all, delete-orphan",
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
