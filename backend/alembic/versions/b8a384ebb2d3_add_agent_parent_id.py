"""add_agent_parent_id

Revision ID: b8a384ebb2d3
Revises: 136608efca4b
Create Date: 2026-08-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8a384ebb2d3"
down_revision: Union[str, Sequence[str], None] = "136608efca4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Add the column first.
    op.add_column(
        "agents",
        sa.Column(
            "parent_agent_id",
            sa.String(length=36),
            nullable=True,
        ),
    )

    # SQLite cannot ALTER TABLE to add a foreign key.
    # Batch mode recreates the table with the FK included.
    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_agents_parent_agent_id_agents",
            "agents",
            ["parent_agent_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # Helpful for parent/child agent lookups.
    op.create_index(
        "ix_agents_parent_agent_id",
        "agents",
        ["parent_agent_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Drop the index first.
    op.drop_index(
        "ix_agents_parent_agent_id",
        table_name="agents",
    )

    # SQLite requires batch mode for removing the FK/column.
    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_agents_parent_agent_id_agents",
            type_="foreignkey",
        )
        batch_op.drop_column("parent_agent_id")