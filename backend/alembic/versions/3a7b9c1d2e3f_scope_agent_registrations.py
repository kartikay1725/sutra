"""scope agent registration requests to a target user

Revision ID: 3a7b9c1d2e3f
Revises: 136608efca4b
Create Date: 2026-08-25

"""

from alembic import op
import sqlalchemy as sa


revision = "3a7b9c1d2e3f"
down_revision = "136608efca4b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table(
        "agent_registration_requests",
        schema=None,
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "requested_for_user_id",
                sa.String(),
                nullable=True,
            )
        )

        batch_op.create_index(
            "ix_agent_registration_requests_requested_for_user_id",
            ["requested_for_user_id"],
            unique=False,
        )

        batch_op.create_foreign_key(
            "fk_agent_registration_requests_requested_for_user_id",
            "users",
            ["requested_for_user_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "agent_registration_requests",
        schema=None,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_agent_registration_requests_requested_for_user_id",
            type_="foreignkey",
        )

        batch_op.drop_index(
            "ix_agent_registration_requests_requested_for_user_id"
        )

        batch_op.drop_column(
            "requested_for_user_id"
        )