from uuid import uuid4

from sqlalchemy import ForeignKey, String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ChangeFile(Base):
    __tablename__ = "change_files"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    change_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("changes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    operation: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    old_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    new_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    additions: Mapped[int] = mapped_column(
        Integer,
        server_default="0",
        nullable=False,
        default=0,
    )

    deletions: Mapped[int] = mapped_column(
        Integer,
        server_default="0",
        nullable=False,
        default=0,
    )
