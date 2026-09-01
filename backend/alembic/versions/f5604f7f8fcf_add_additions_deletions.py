"""add_additions_deletions

Revision ID: f5604f7f8fcf
Revises: fa25ab087fe3
Create Date: 2026-08-28 22:26:54.355479

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5604f7f8fcf'
down_revision: Union[str, Sequence[str], None] = 'fa25ab087fe3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('change_files', sa.Column('additions', sa.Integer(), server_default='0', nullable=False))
    op.add_column('change_files', sa.Column('deletions', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('change_files', 'deletions')
    op.drop_column('change_files', 'additions')

