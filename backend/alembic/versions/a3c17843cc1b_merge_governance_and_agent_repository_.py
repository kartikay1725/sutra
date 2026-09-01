"""merge governance and agent repository access heads

Revision ID: a3c17843cc1b
Revises: c4d5e6f70819, d5e6f708192a
Create Date: 2026-08-25 20:39:15.113603

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c17843cc1b'
down_revision: Union[str, Sequence[str], None] = ('c4d5e6f70819', 'd5e6f708192a')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
