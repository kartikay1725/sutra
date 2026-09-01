"""add_branch_protection_rules_table

Revision ID: 8a0b234c5678
Revises: 7f9a123b4567
Create Date: 2026-08-14 22:38:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a0b234c5678'
down_revision: Union[str, Sequence[str], None] = '7f9a123b4567'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'branch_protection_rules',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('repository_id', sa.String(length=36), nullable=False),
        sa.Column('branch_pattern', sa.String(length=255), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('required_approvals', sa.Integer(), server_default='1', nullable=False),
        sa.Column('require_change_review', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('require_clean_conflict', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('require_resolved_threads', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('require_agent_review', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('require_no_blocking_agent_findings', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('allow_author_self_approval', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_by', sa.String(length=36), nullable=False),
        sa.Column('updated_by', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('required_approvals >= 0', name='ck_branch_protection_req_approvals'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repository_id', 'branch_pattern', name='uq_branch_protection_repo_pattern')
    )
    op.create_index(op.f('ix_branch_protection_rules_repository_id'), 'branch_protection_rules', ['repository_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_branch_protection_rules_repository_id'), table_name='branch_protection_rules')
    op.drop_table('branch_protection_rules')
