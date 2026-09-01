"""add_ci_jobs_table

Revision ID: 9b1c345d6789
Revises: 8a0b234c5678
Create Date: 2026-08-14 22:51:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b1c345d6789'
down_revision: Union[str, Sequence[str], None] = '8a0b234c5678'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'ci_jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('pull_request_id', sa.String(length=36), nullable=False),
        sa.Column('repository_id', sa.String(length=36), nullable=False),
        sa.Column('change_id', sa.String(length=36), nullable=False),
        sa.Column('commit_sha', sa.String(length=64), nullable=False),
        sa.Column('target_branch', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='queued', nullable=False),
        sa.Column('trigger', sa.String(length=50), server_default='pull_request', nullable=False),
        sa.Column('runner_type', sa.String(length=50), server_default='isolated_process', nullable=False),
        sa.Column('exit_code', sa.Integer(), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('output_log', sa.Text(), nullable=True),
        sa.Column('worker_id', sa.String(length=64), nullable=True),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('queued', 'running', 'passed', 'failed', 'cancelled', 'timed_out')", name='ck_ci_jobs_status'),
        sa.ForeignKeyConstraint(['change_id'], ['changes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pull_request_id'], ['pull_requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ci_jobs_change_id'), 'ci_jobs', ['change_id'], unique=False)
    op.create_index(op.f('ix_ci_jobs_commit_sha'), 'ci_jobs', ['commit_sha'], unique=False)
    op.create_index(op.f('ix_ci_jobs_lease_expires_at'), 'ci_jobs', ['lease_expires_at'], unique=False)
    op.create_index(op.f('ix_ci_jobs_pull_request_id'), 'ci_jobs', ['pull_request_id'], unique=False)
    op.create_index(op.f('ix_ci_jobs_repository_id'), 'ci_jobs', ['repository_id'], unique=False)
    op.create_index(op.f('ix_ci_jobs_status'), 'ci_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_ci_jobs_worker_id'), 'ci_jobs', ['worker_id'], unique=False)

    op.add_column('branch_protection_rules', sa.Column('require_ci_passed', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('branch_protection_rules', 'require_ci_passed')
    op.drop_index(op.f('ix_ci_jobs_worker_id'), table_name='ci_jobs')
    op.drop_index(op.f('ix_ci_jobs_status'), table_name='ci_jobs')
    op.drop_index(op.f('ix_ci_jobs_repository_id'), table_name='ci_jobs')
    op.drop_index(op.f('ix_ci_jobs_pull_request_id'), table_name='ci_jobs')
    op.drop_index(op.f('ix_ci_jobs_lease_expires_at'), table_name='ci_jobs')
    op.drop_index(op.f('ix_ci_jobs_commit_sha'), table_name='ci_jobs')
    op.drop_index(op.f('ix_ci_jobs_change_id'), table_name='ci_jobs')
    op.drop_table('ci_jobs')
