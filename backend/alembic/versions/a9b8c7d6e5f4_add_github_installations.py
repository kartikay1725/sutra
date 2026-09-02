"""add_github_installations

Revision ID: a9b8c7d6e5f4
Revises: f7a8b9c0d1e2
Create Date: 2026-09-02 08:00:00.000000

Adds:
  - github_installations table (user → GitHub App installation mapping)
  - provider_type, external_id, github_installation_id, provider_owner columns to repositories
  - Partial unique index on repositories(provider_type, external_id) WHERE external_id IS NOT NULL
"""

from alembic import op
import sqlalchemy as sa

revision = "a9b8c7d6e5f4"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Create github_installations table
    # -----------------------------------------------------------------------
    op.create_table(
        "github_installations",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("github_installation_id", sa.BigInteger(), nullable=False),
        sa.Column("github_account_id", sa.BigInteger(), nullable=False),
        sa.Column("github_account_login", sa.String(100), nullable=False),
        sa.Column(
            "target_type",
            sa.String(20),
            nullable=False,
            server_default="User",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "ix_github_installations_user_id",
        "github_installations",
        ["user_id"],
    )

    op.create_index(
        "ix_github_installations_github_installation_id",
        "github_installations",
        ["github_installation_id"],
    )

    op.create_unique_constraint(
        "uq_github_installation_id",
        "github_installations",
        ["github_installation_id"],
    )

    # -----------------------------------------------------------------------
    # 2. Add provider identity columns to repositories
    # -----------------------------------------------------------------------
    op.add_column(
        "repositories",
        sa.Column(
            "provider_type",
            sa.String(20),
            nullable=False,
            server_default="local",
        ),
    )

    op.add_column(
        "repositories",
        sa.Column(
            "external_id",
            sa.String(64),
            nullable=True,
        ),
    )

    op.add_column(
        "repositories",
        sa.Column(
            "github_installation_id",
            sa.BigInteger(),
            nullable=True,
        ),
    )

    op.add_column(
        "repositories",
        sa.Column(
            "provider_owner",
            sa.String(100),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_repositories_github_installation_id",
        "repositories",
        ["github_installation_id"],
    )

    # Partial unique index:
    # No two repositories can share the same provider/external identity.
    # PostgreSQL-specific syntax; SUTRA targets PostgreSQL/Supabase.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_repo_provider_external
        ON repositories (provider_type, external_id)
        WHERE external_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS uq_repo_provider_external"
    )

    op.drop_index(
        "ix_repositories_github_installation_id",
        table_name="repositories",
    )

    op.drop_column("repositories", "provider_owner")
    op.drop_column("repositories", "github_installation_id")
    op.drop_column("repositories", "external_id")
    op.drop_column("repositories", "provider_type")

    op.drop_constraint(
        "uq_github_installation_id",
        "github_installations",
        type_="unique",
    )

    op.drop_index(
        "ix_github_installations_github_installation_id",
        table_name="github_installations",
    )

    op.drop_index(
        "ix_github_installations_user_id",
        table_name="github_installations",
    )

    op.drop_table("github_installations")