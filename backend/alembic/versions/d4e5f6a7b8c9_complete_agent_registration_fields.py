"""complete agent registration request fields

Revision ID: d4e5f6a7b8c9
Revises: fb26a66adb76
Create Date: 2026-09-02

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "fb26a66adb76"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the registration fields required by AgentRegistrationRequest."""

    with op.batch_alter_table(
        "agent_registration_requests",
        schema=None,
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "requested_repo_name",
                sa.String(length=255),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "new_repo",
                sa.Boolean(),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "temporary_token",
                sa.String(length=255),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "temporary_token_hash",
                sa.String(length=255),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "is_temporary_token_used",
                sa.Boolean(),
                nullable=True,
            )
        )

    # Normalize NULL values before enforcing NOT NULL.
    #
    # This migration targets PostgreSQL in production, so PostgreSQL
    # boolean literals are used here.
    op.execute(
        sa.text(
            """
            UPDATE agent_registration_requests
            SET new_repo = FALSE
            WHERE new_repo IS NULL
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE agent_registration_requests
            SET is_temporary_token_used = FALSE
            WHERE is_temporary_token_used IS NULL
            """
        )
    )

    # Now enforce NOT NULL on the boolean fields.
    with op.batch_alter_table(
        "agent_registration_requests",
        schema=None,
    ) as batch_op:
        batch_op.alter_column(
            "new_repo",
            existing_type=sa.Boolean(),
            nullable=False,
        )

        batch_op.alter_column(
            "is_temporary_token_used",
            existing_type=sa.Boolean(),
            nullable=False,
        )


def downgrade() -> None:
    """Remove the extended registration fields."""

    with op.batch_alter_table(
        "agent_registration_requests",
        schema=None,
    ) as batch_op:
        batch_op.drop_column("is_temporary_token_used")
        batch_op.drop_column("temporary_token_hash")
        batch_op.drop_column("temporary_token")
        batch_op.drop_column("new_repo")
        batch_op.drop_column("requested_repo_name")