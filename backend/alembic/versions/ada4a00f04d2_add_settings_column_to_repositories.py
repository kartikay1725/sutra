"""Add settings column to repositories

Revision ID: ada4a00f04d2
Revises: 86b09d8b5bc4
Create Date: 2026-08-23 17:58:43.403192

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ada4a00f04d2'
down_revision: Union[str, Sequence[str], None] = '86b09d8b5bc4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('repositories', sa.Column('settings', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('repositories') as batch_op:
        batch_op.drop_column('settings')
