"""add_agent_registration_requests_table

Revision ID: 136608efca4b
Revises: c1d2e3f4a5b6
Create Date: 2026-08-21 09:38:15.275892
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "136608efca4b"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_index_names(table_name: str) -> set[str]:
    """Return the existing index names for a table."""
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
    # Agent registration requests
    # ------------------------------------------------------------------
    op.create_table(
        "agent_registration_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("agent_name", sa.String(length=120), nullable=False),
        sa.Column("agent_description", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(length=120), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("requested_capabilities", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("polling_token_hash", sa.String(length=255), nullable=False),
        sa.Column("permanent_token_encrypted", sa.Text(), nullable=True),
        sa.Column("approved_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_agent_registration_requests_expires_at",
        "agent_registration_requests",
        ["expires_at"],
        unique=False,
    )

    op.create_index(
        "ix_agent_registration_requests_status",
        "agent_registration_requests",
        ["status"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # Changes table
    #
    # SQLite does not support ALTER TABLE for arbitrary constraints,
    # so batch mode is required.
    #
    # The baseline schema already contains:
    #   ix_changes_operation_key
    #
    # Therefore we do NOT recreate that index here.
    # ------------------------------------------------------------------
    

    # ------------------------------------------------------------------
    # Git push events
    #
    # Earlier migrations do not guarantee the two legacy indexes exist
    # on SQLite. Only drop them when they are actually present.
    # ------------------------------------------------------------------
    existing_indexes = _get_index_names("git_push_events")

    if "ix_git_push_events_status_lease_expires_at" in existing_indexes:
        op.drop_index(
            "ix_git_push_events_status_lease_expires_at",
            table_name="git_push_events",
        )

    if "ix_git_push_events_status_next_attempt_at_created_at" in existing_indexes:
        op.drop_index(
            "ix_git_push_events_status_next_attempt_at_created_at",
            table_name="git_push_events",
        )

    existing_indexes = _get_index_names("git_push_events")

    if "ix_git_push_events_integrity_hash" not in existing_indexes:
        op.create_index(
            "ix_git_push_events_integrity_hash",
            "git_push_events",
            ["integrity_hash"],
            unique=False,
        )


def downgrade() -> None:
    """Downgrade schema."""

    # ------------------------------------------------------------------
    # Git push events
    # ------------------------------------------------------------------
    existing_indexes = _get_index_names("git_push_events")

    if "ix_git_push_events_integrity_hash" in existing_indexes:
        op.drop_index(
            "ix_git_push_events_integrity_hash",
            table_name="git_push_events",
        )

    existing_indexes = _get_index_names("git_push_events")

    if (
        "ix_git_push_events_status_next_attempt_at_created_at"
        not in existing_indexes
    ):
        op.create_index(
            "ix_git_push_events_status_next_attempt_at_created_at",
            "git_push_events",
            ["status", "next_attempt_at", "created_at"],
            unique=False,
        )

    existing_indexes = _get_index_names("git_push_events")

    if "ix_git_push_events_status_lease_expires_at" not in existing_indexes:
        op.create_index(
            "ix_git_push_events_status_lease_expires_at",
            "git_push_events",
            ["status", "lease_expires_at"],
            unique=False,
        )

    # ------------------------------------------------------------------
    # Changes table
    # ------------------------------------------------------------------
   

    

    # ------------------------------------------------------------------
    # Agent registration requests
    # ------------------------------------------------------------------
    existing_indexes = _get_index_names("agent_registration_requests")

    if "ix_agent_registration_requests_status" in existing_indexes:
        op.drop_index(
            "ix_agent_registration_requests_status",
            table_name="agent_registration_requests",
        )

    existing_indexes = _get_index_names("agent_registration_requests")

    if "ix_agent_registration_requests_expires_at" in existing_indexes:
        op.drop_index(
            "ix_agent_registration_requests_expires_at",
            table_name="agent_registration_requests",
        )

    op.drop_table("agent_registration_requests")