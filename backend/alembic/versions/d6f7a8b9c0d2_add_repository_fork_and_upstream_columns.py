"""add_repository_fork_and_upstream_columns

Revision ID: d6f7a8b9c0d2
Revises: c5e91234abcd
Create Date: 2026-09-14 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6f7a8b9c0d2'
down_revision: Union[str, Sequence[str], None] = 'c5e91234abcd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'repositories',
        sa.Column('connection_type', sa.String(32), nullable=False, server_default='owned')
    )
    op.add_column(
        'repositories',
        sa.Column('upstream_repository_id', sa.String(36), sa.ForeignKey('repositories.id', ondelete='SET NULL'), nullable=True)
    )
    op.add_column(
        'repositories',
        sa.Column('upstream_url', sa.String(500), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('repositories', 'upstream_url')
    op.drop_column('repositories', 'upstream_repository_id')
    op.drop_column('repositories', 'connection_type')
