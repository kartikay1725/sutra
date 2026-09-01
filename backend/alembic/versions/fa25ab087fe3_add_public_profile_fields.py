"""add public profile fields

Revision ID: fa25ab087fe3
Revises: a3c17843cc1b
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "fa25ab087fe3"
down_revision: Union[str, Sequence[str], None] = "a3c17843cc1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {
        column["name"]: column
        for column in inspect(bind).get_columns("users")
    }

    if "full_name" not in existing:
        op.add_column(
            "users",
            sa.Column(
                "full_name",
                sa.String(length=255),
                nullable=True,
            ),
        )

    if "bio" not in existing:
        op.add_column(
            "users",
            sa.Column(
                "bio",
                sa.String(length=1000),
                nullable=True,
            ),
        )

    if "social_links" not in existing:
        op.add_column(
            "users",
            sa.Column(
                "social_links",
                sa.JSON(),
                nullable=True,
                server_default=sa.text("'{}'"),
            ),
        )

        op.execute(
            sa.text(
                "UPDATE users "
                "SET social_links = '{}' "
                "WHERE social_links IS NULL"
            )
        )
    else:
        op.execute(
            sa.text(
                "UPDATE users "
                "SET social_links = '{}' "
                "WHERE social_links IS NULL"
            )
        )

    # SQLite requires batch mode to alter nullability safely.
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "social_links",
            existing_type=sa.JSON(),
            nullable=False,
            server_default=None,
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("social_links")
        batch_op.drop_column("bio")
        batch_op.drop_column("full_name")
