from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Issue(Base):
    __tablename__ = "issues"

    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "github_issue_number",
            name="uq_issue_repository_github_number",
        ),
    )

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

    # GitHub is the source of truth.
    github_issue_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    github_issue_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    github_html_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # GitHub issue state: open / closed
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="open",
        index=True,
    )

    # "human" or "agent"
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="human",
        index=True,
    )

    # SUTRA provenance.
    # These remain nullable because normal GitHub issues
    # have no SUTRA agent/session/task provenance.
    agent_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    agent_session_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    task_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    # The database column is actor_id.
    # An Actor may represent a human or an agent.
    actor_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("actors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Snapshot fields for fast display/search.
    github_author_login: Mapped[str | None] = mapped_column(
        String(255),
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

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    repository = relationship("Repository")
    actor = relationship("Actor")

    comments = relationship(
        "IssueComment",
        back_populates="issue",
        cascade="all, delete-orphan",
    )

    @property
    def author_id(self) -> str | None:
        """
        Backward-compatible Python alias.

        Existing SUTRA code/tests may still refer to
        issue.author_id, but the authoritative DB column
        is actor_id.
        """
        return self.actor_id

    @author_id.setter
    def author_id(self, value: str | None) -> None:
        self.actor_id = value


class IssueComment(Base):
    __tablename__ = "issue_comments"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    issue_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # GitHub comment identity.
    github_comment_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    github_html_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Issue comments still legitimately use author_id.
    author_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("actors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    github_author_login: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    body: Mapped[str] = mapped_column(
        Text,
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

    issue = relationship(
        "Issue",
        back_populates="comments",
    )

    author = relationship("Actor")