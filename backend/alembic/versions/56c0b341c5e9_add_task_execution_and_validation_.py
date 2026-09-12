"""add_task_execution_and_validation_summaries

Revision ID: 56c0b341c5e9
Revises: 79c24d6dd026
Create Date: 2026-09-12 21:14:35.469971

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '56c0b341c5e9'
down_revision: Union[str, Sequence[str], None] = '79c24d6dd026'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tasks', sa.Column('execution_summary', sa.Text(), nullable=True))
    op.add_column('tasks', sa.Column('validation_summary', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tasks', 'validation_summary')
    op.drop_column('tasks', 'execution_summary')
