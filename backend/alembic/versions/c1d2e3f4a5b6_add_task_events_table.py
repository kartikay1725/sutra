"""add task events and merge existing migration heads

Revision ID: c1d2e3f4a5b6
Revises: 7f9a123b4567, bbccd1f1eff2
Create Date: 2026-08-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = (
    "7f9a123b4567",
    "bbccd1f1eff2",
)

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_events",

        sa.Column(
            "id",
            sa.String(length=36),
            nullable=False,
        ),

        sa.Column(
            "task_id",
            sa.String(length=36),
            nullable=False,
        ),

        sa.Column(
            "actor_id",
            sa.String(length=36),
            nullable=True,
        ),

        sa.Column(
            "session_id",
            sa.String(length=36),
            nullable=True,
        ),

        sa.Column(
            "event_type",
            sa.String(length=64),
            nullable=False,
        ),

        sa.Column(
            "from_status",
            sa.String(length=30),
            nullable=True,
        ),

        sa.Column(
            "to_status",
            sa.String(length=30),
            nullable=True,
        ),

        sa.Column(
            "reason",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "metadata_json",
            sa.Text(),
            nullable=False,
            server_default="{}",
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["session_id"],
            ["agent_sessions.id"],
            ondelete="SET NULL",
        ),

        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_task_events_task_id",
        "task_events",
        ["task_id"],
        unique=False,
    )

    op.create_index(
        "ix_task_events_actor_id",
        "task_events",
        ["actor_id"],
        unique=False,
    )

    op.create_index(
        "ix_task_events_session_id",
        "task_events",
        ["session_id"],
        unique=False,
    )

    op.create_index(
        "ix_task_events_event_type",
        "task_events",
        ["event_type"],
        unique=False,
    )

    op.create_index(
        "ix_task_events_created_at",
        "task_events",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_task_events_created_at",
        table_name="task_events",
    )

    op.drop_index(
        "ix_task_events_event_type",
        table_name="task_events",
    )

    op.drop_index(
        "ix_task_events_session_id",
        table_name="task_events",
    )

    op.drop_index(
        "ix_task_events_actor_id",
        table_name="task_events",
    )

    op.drop_index(
        "ix_task_events_task_id",
        table_name="task_events",
    )

    op.drop_table("task_events")
