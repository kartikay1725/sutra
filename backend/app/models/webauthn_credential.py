from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, String, ForeignKey, LargeBinary, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class WebAuthnCredential(Base):
    __tablename__ = "webauthn_credentials"

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

    credential_id: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        unique=True,
        index=True,
    )

    public_key: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )

    sign_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    transports: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
