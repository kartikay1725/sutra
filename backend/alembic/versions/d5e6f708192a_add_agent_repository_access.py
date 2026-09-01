"""add repository scoped agent access

Revision ID: d5e6f708192a
Revises: b0987aa3faa5
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "d5e6f708192a"
down_revision = "b0987aa3faa5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "agent_repository_access" in inspector.get_table_names():
        return

    op.create_table(
        "agent_repository_access",
        sa.Column(
            "id",
            sa.String(36),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            sa.String(36),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            sa.String(36),
            nullable=False,
        ),
        sa.Column(
            "permissions",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "agent_id",
            "repository_id",
            name="uq_agent_repository_access_agent_repo",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "agent_repository_access" in inspector.get_table_names():
        op.drop_table("agent_repository_access")