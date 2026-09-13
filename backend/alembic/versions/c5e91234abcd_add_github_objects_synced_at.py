"""add_github_objects_synced_at_to_repositories

Revision ID: c5e91234abcd
Revises: 56c0b341c5e9
Create Date: 2026-09-13 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5e91234abcd'
down_revision: Union[str, Sequence[str], None] = '56c0b341c5e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'repositories',
        sa.Column('github_objects_synced_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('repositories', 'github_objects_synced_at')
