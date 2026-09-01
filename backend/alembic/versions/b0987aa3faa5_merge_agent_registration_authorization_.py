"""merge agent registration authorization heads

Revision ID: b0987aa3faa5
Revises: 1670cfccff2e, 3a7b9c1d2e3f
Create Date: 2026-08-25 18:01:43.540047

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0987aa3faa5'
down_revision: Union[str, Sequence[str], None] = ('1670cfccff2e', '3a7b9c1d2e3f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
