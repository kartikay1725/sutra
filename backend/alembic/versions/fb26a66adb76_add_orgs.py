"""add_orgs

Revision ID: fb26a66adb76
Revises: 7ebd1d922b83
Create Date: 2026-08-21 11:18:56.691038

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fb26a66adb76"
down_revision: Union[str, Sequence[str], None] = "7ebd1d922b83"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_names(table_name: str) -> set[str]:
    """Return existing index names for a table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    return {
        index["name"]
        for index in inspector.get_indexes(table_name)
        if index.get("name")
    }


def upgrade() -> None:
    """Upgrade schema."""

    # ------------------------------------------------------------------
    # Organizations
    # ------------------------------------------------------------------
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_organizations_name",
        "organizations",
        ["name"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # Actor follows
    # ------------------------------------------------------------------
    op.create_table(
        "actor_follows",
        sa.Column("follower_id", sa.String(length=36), nullable=False),
        sa.Column("following_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["follower_id"],
            ["actors.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["following_id"],
            ["actors.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "follower_id",
            "following_id",
        ),
    )

    op.create_index(
        "ix_actor_follows_follower_id",
        "actor_follows",
        ["follower_id"],
        unique=False,
    )

    op.create_index(
        "ix_actor_follows_following_id",
        "actor_follows",
        ["following_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # Organization members
    # ------------------------------------------------------------------
    op.create_table(
        "organization_members",
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "user_id",
        ),
    )

    op.create_index(
        "ix_organization_members_organization_id",
        "organization_members",
        ["organization_id"],
        unique=False,
    )

    op.create_index(
        "ix_organization_members_user_id",
        "organization_members",
        ["user_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # Repository stars
    # ------------------------------------------------------------------
    op.create_table(
        "repository_stars",
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["actors.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "actor_id",
            "repository_id",
        ),
    )

    op.create_index(
        "ix_repository_stars_actor_id",
        "repository_stars",
        ["actor_id"],
        unique=False,
    )

    op.create_index(
        "ix_repository_stars_repository_id",
        "repository_stars",
        ["repository_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # Repository owner FK
    #
    # Earlier schema versions may have repositories.owner_id pointing
    # to users.id. The application model is actor-based, so migrate
    # that FK to actors.id.
    #
    # SQLite requires batch mode for changing foreign keys.
    # ------------------------------------------------------------------
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    repository_fks = inspector.get_foreign_keys("repositories")

    owner_fk = next(
        (
            fk
            for fk in repository_fks
            if fk.get("constrained_columns") == ["owner_id"]
        ),
        None,
    )

    if owner_fk is not None:
        referred_table = owner_fk.get("referred_table")

        if referred_table != "actors":
            old_fk_name = owner_fk.get("name")

            # SQLite commonly has unnamed foreign keys. During batch
            # reflection, give them deterministic names so they can
            # be dropped safely.
            if not old_fk_name:
                old_fk_name = "fk_repositories_owner_id_users"

            naming_convention = {
                "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
            }

            with op.batch_alter_table(
                "repositories",
                schema=None,
                naming_convention=naming_convention,
            ) as batch_op:
                batch_op.drop_constraint(
                    old_fk_name,
                    type_="foreignkey",
                )

                batch_op.create_foreign_key(
                    "fk_repositories_owner_id_actors",
                    "actors",
                    ["owner_id"],
                    ["id"],
                    ondelete="CASCADE",
                )


def downgrade() -> None:
    """Downgrade schema."""

    # ------------------------------------------------------------------
    # Restore repository owner FK to users.id
    # ------------------------------------------------------------------
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    repository_fks = inspector.get_foreign_keys("repositories")

    owner_fk = next(
        (
            fk
            for fk in repository_fks
            if fk.get("constrained_columns") == ["owner_id"]
        ),
        None,
    )

    if owner_fk is not None:
        referred_table = owner_fk.get("referred_table")

        if referred_table == "actors":
            old_fk_name = owner_fk.get("name")

            if not old_fk_name:
                old_fk_name = "fk_repositories_owner_id_actors"

            naming_convention = {
                "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
            }

            with op.batch_alter_table(
                "repositories",
                schema=None,
                naming_convention=naming_convention,
            ) as batch_op:
                batch_op.drop_constraint(
                    old_fk_name,
                    type_="foreignkey",
                )

                batch_op.create_foreign_key(
                    "fk_repositories_owner_id_users",
                    "users",
                    ["owner_id"],
                    ["id"],
                    ondelete="CASCADE",
                )

    # ------------------------------------------------------------------
    # Repository stars
    # ------------------------------------------------------------------
    existing = _index_names("repository_stars")

    if "ix_repository_stars_repository_id" in existing:
        op.drop_index(
            "ix_repository_stars_repository_id",
            table_name="repository_stars",
        )

    existing = _index_names("repository_stars")

    if "ix_repository_stars_actor_id" in existing:
        op.drop_index(
            "ix_repository_stars_actor_id",
            table_name="repository_stars",
        )

    op.drop_table("repository_stars")

    # ------------------------------------------------------------------
    # Organization members
    # ------------------------------------------------------------------
    existing = _index_names("organization_members")

    if "ix_organization_members_user_id" in existing:
        op.drop_index(
            "ix_organization_members_user_id",
            table_name="organization_members",
        )

    existing = _index_names("organization_members")

    if "ix_organization_members_organization_id" in existing:
        op.drop_index(
            "ix_organization_members_organization_id",
            table_name="organization_members",
        )

    op.drop_table("organization_members")

    # ------------------------------------------------------------------
    # Actor follows
    # ------------------------------------------------------------------
    existing = _index_names("actor_follows")

    if "ix_actor_follows_following_id" in existing:
        op.drop_index(
            "ix_actor_follows_following_id",
            table_name="actor_follows",
        )

    existing = _index_names("actor_follows")

    if "ix_actor_follows_follower_id" in existing:
        op.drop_index(
            "ix_actor_follows_follower_id",
            table_name="actor_follows",
        )

    op.drop_table("actor_follows")

    # ------------------------------------------------------------------
    # Organizations
    # ------------------------------------------------------------------
    existing = _index_names("organizations")

    if "ix_organizations_name" in existing:
        op.drop_index(
            "ix_organizations_name",
            table_name="organizations",
        )

    op.drop_table("organizations")