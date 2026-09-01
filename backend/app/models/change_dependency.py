from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ChangeDependency(Base):
    __tablename__ = "change_dependencies"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    source_change_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("changes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    target_change_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("changes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    relationship: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
