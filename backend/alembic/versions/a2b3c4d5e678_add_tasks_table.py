"""add_tasks_table

Revision ID: a2b3c4d5e678
Revises: 9b1c345d6789
Create Date: 2026-08-14 23:43:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e678'
down_revision: Union[str, Sequence[str], None] = '9b1c345d6789'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'tasks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('repository_id', sa.String(length=36), nullable=False),
        sa.Column('created_by', sa.String(length=36), nullable=False),
        sa.Column('assigned_agent_id', sa.String(length=36), nullable=True),
        sa.Column('assigned_user_id', sa.String(length=36), nullable=True),
        sa.Column('resulting_change_id', sa.String(length=36), nullable=True),
        sa.Column('resulting_pull_request_id', sa.String(length=36), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='open', nullable=False),
        sa.Column('priority', sa.String(length=20), server_default='medium', nullable=False),
        sa.Column('task_type', sa.String(length=30), server_default='feature', nullable=False),
        sa.Column('source', sa.String(length=30), server_default='user', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('open', 'assigned', 'in_progress', 'blocked', 'completed', 'cancelled')", name='ck_tasks_status'),
        sa.CheckConstraint("priority IN ('low', 'medium', 'high', 'critical')", name='ck_tasks_priority'),
        sa.CheckConstraint("task_type IN ('feature', 'bugfix', 'refactor', 'security', 'documentation')", name='ck_tasks_type'),
        sa.ForeignKeyConstraint(['assigned_agent_id'], ['agents.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['assigned_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resulting_change_id'], ['changes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resulting_pull_request_id'], ['pull_requests.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tasks_assigned_agent_id'), 'tasks', ['assigned_agent_id'], unique=False)
    op.create_index(op.f('ix_tasks_assigned_user_id'), 'tasks', ['assigned_user_id'], unique=False)
    op.create_index(op.f('ix_tasks_created_by'), 'tasks', ['created_by'], unique=False)
    op.create_index(op.f('ix_tasks_repository_id'), 'tasks', ['repository_id'], unique=False)
    op.create_index(op.f('ix_tasks_resulting_change_id'), 'tasks', ['resulting_change_id'], unique=False)
    op.create_index(op.f('ix_tasks_resulting_pull_request_id'), 'tasks', ['resulting_pull_request_id'], unique=False)
    op.create_index(op.f('ix_tasks_status'), 'tasks', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_tasks_status'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_resulting_pull_request_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_resulting_change_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_repository_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_created_by'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_assigned_user_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_assigned_agent_id'), table_name='tasks')
    op.drop_table('tasks')
