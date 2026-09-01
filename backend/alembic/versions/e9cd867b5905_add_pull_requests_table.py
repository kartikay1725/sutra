"""add_pull_requests_table

Revision ID: e9cd867b5905
Revises: 1c77ea59469c
Create Date: 2026-08-14 14:39:41.276836

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9cd867b5905'
down_revision: Union[str, Sequence[str], None] = '1c77ea59469c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'pull_requests',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('repository_id', sa.String(length=36), nullable=False),
        sa.Column('author_id', sa.String(length=36), nullable=False),
        sa.Column('source_change_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('target_branch', sa.String(length=255), nullable=False),
        sa.Column('source_commit', sa.String(length=64), nullable=True),
        sa.Column('target_commit', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='open', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('merged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'open', 'approved', 'merged', 'closed', 'rejected')",
            name='ck_pull_requests_status'
        ),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_change_id'], ['changes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_change_id', name='uq_pull_requests_source_change_id')
    )
    op.create_index(op.f('ix_pull_requests_author_id'), 'pull_requests', ['author_id'], unique=False)
    op.create_index(op.f('ix_pull_requests_repository_id'), 'pull_requests', ['repository_id'], unique=False)
    op.create_index(op.f('ix_pull_requests_source_change_id'), 'pull_requests', ['source_change_id'], unique=False)
    op.create_index(op.f('ix_pull_requests_status'), 'pull_requests', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_pull_requests_status'), table_name='pull_requests')
    op.drop_index(op.f('ix_pull_requests_source_change_id'), table_name='pull_requests')
    op.drop_index(op.f('ix_pull_requests_repository_id'), table_name='pull_requests')
    op.drop_index(op.f('ix_pull_requests_author_id'), table_name='pull_requests')
    op.drop_table('pull_requests')
