"""add task agent execution leases

Revision ID: bbccd1f1eff2
Revises: b3c4d5e6f789
Create Date: 2026-08-16 17:41:18.021976

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bbccd1f1eff2'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f789'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "claimed_by_session_id",
            sa.String(length=36),
            nullable=True,
        ),
    )

    op.add_column(
        "tasks",
        sa.Column(
            "lease_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # SQLite does not support ALTER TABLE ... ADD CONSTRAINT.
    # Alembic batch mode rebuilds the table and recreates the FK safely.
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_tasks_claimed_by_session_id_agent_sessions",
            "agent_sessions",
            ["claimed_by_session_id"],
            ["id"],
            ondelete="SET NULL",
        )

        batch_op.create_index(
            "ix_tasks_claimed_by_session_id",
            ["claimed_by_session_id"],
            unique=False,
        )

        batch_op.create_index(
            "ix_tasks_lease_expires_at",
            ["lease_expires_at"],
            unique=False,
        )

def downgrade() -> None:
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_index("ix_tasks_lease_expires_at")
        batch_op.drop_index("ix_tasks_claimed_by_session_id")
        batch_op.drop_constraint(
            "fk_tasks_claimed_by_session_id_agent_sessions",
            type_="foreignkey",
        )
        batch_op.drop_column("lease_expires_at")
        batch_op.drop_column("claimed_by_session_id")