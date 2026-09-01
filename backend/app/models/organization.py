from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, PrimaryKeyConstraint, Text
from app.db.session import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True)  # Matches an actor.id
    name = Column(String(255), unique=True, index=True, nullable=False) # slug/username equivalent
    display_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    role = Column(String(50), nullable=False, default="member") # "owner", "admin", "member"
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("organization_id", "user_id"),
    )
