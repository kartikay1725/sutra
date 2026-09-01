"""add_agent_sessions_table

Revision ID: b3c4d5e6f789
Revises: a2b3c4d5e678
Create Date: 2026-08-16

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3c4d5e6f789"
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e678"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column(
            "id",
            sa.String(length=36),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            sa.String(length=36),
            nullable=False,
        ),
        sa.Column(
            "token_hash",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "token_prefix",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_agent_sessions_agent_id",
        "agent_sessions",
        ["agent_id"],
        unique=False,
    )

    op.create_index(
        "ix_agent_sessions_token_prefix",
        "agent_sessions",
        ["token_prefix"],
        unique=False,
    )

    op.create_index(
        "ix_agent_sessions_status",
        "agent_sessions",
        ["status"],
        unique=False,
    )

    op.create_index(
        "ix_agent_sessions_expires_at",
        "agent_sessions",
        ["expires_at"],
        unique=False,
    )

    op.create_index(
        "ix_agent_sessions_last_seen_at",
        "agent_sessions",
        ["last_seen_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_sessions_last_seen_at",
        table_name="agent_sessions",
    )

    op.drop_index(
        "ix_agent_sessions_expires_at",
        table_name="agent_sessions",
    )

    op.drop_index(
        "ix_agent_sessions_status",
        table_name="agent_sessions",
    )

    op.drop_index(
        "ix_agent_sessions_token_prefix",
        table_name="agent_sessions",
    )

    op.drop_index(
        "ix_agent_sessions_agent_id",
        table_name="agent_sessions",
    )

    op.drop_table("agent_sessions")