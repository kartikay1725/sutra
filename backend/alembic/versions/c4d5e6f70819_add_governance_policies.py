"""add persistent governance policies

Revision ID: c4d5e6f70819
Revises: b0987aa3faa5
"""

from alembic import op
import sqlalchemy as sa

revision = "c4d5e6f70819"
down_revision = "b0987aa3faa5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "governance_policies",
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("enforce_branch_protection", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("minimum_pr_approvals", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("restrict_public_repositories", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("require_signed_commits", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("organization_id"),
    )


def downgrade() -> None:
    op.drop_table("governance_policies")
