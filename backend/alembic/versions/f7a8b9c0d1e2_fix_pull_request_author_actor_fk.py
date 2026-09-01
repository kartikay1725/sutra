"""fix pull request author foreign key to actors

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-02

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change pull_requests.author_id from users.id to actors.id."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    foreign_keys = inspector.get_foreign_keys("pull_requests")

    author_fk = next(
        (
            fk
            for fk in foreign_keys
            if fk.get("constrained_columns") == ["author_id"]
        ),
        None,
    )

    # Nothing to do if the correct FK already exists.
    if author_fk is not None and author_fk.get("referred_table") == "actors":
        return

    # SQLite requires batch mode to alter foreign keys.
    naming_convention = {
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
    }

    with op.batch_alter_table(
        "pull_requests",
        schema=None,
        naming_convention=naming_convention,
    ) as batch_op:

        # The original FK was unnamed in the SQLite database.
        old_fk_name = None

        if author_fk is not None:
            old_fk_name = author_fk.get("name")

        if not old_fk_name:
            old_fk_name = "fk_pull_requests_author_id_users"

        batch_op.drop_constraint(
            old_fk_name,
            type_="foreignkey",
        )

        batch_op.create_foreign_key(
            "fk_pull_requests_author_id_actors",
            "actors",
            ["author_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    """Restore pull_requests.author_id → users.id."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    foreign_keys = inspector.get_foreign_keys("pull_requests")

    author_fk = next(
        (
            fk
            for fk in foreign_keys
            if fk.get("constrained_columns") == ["author_id"]
        ),
        None,
    )

    if author_fk is None or author_fk.get("referred_table") != "actors":
        return

    naming_convention = {
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
    }

    old_fk_name = author_fk.get("name")

    if not old_fk_name:
        old_fk_name = "fk_pull_requests_author_id_actors"

    with op.batch_alter_table(
        "pull_requests",
        schema=None,
        naming_convention=naming_convention,
    ) as batch_op:

        batch_op.drop_constraint(
            old_fk_name,
            type_="foreignkey",
        )

        batch_op.create_foreign_key(
            "fk_pull_requests_author_id_users",
            "users",
            ["author_id"],
            ["id"],
            ondelete="RESTRICT",
        )