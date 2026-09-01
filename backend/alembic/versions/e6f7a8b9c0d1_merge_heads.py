"""merge migration heads

Revision ID: e6f7a8b9c0d1
Revises: a1b2c3d4e5f6, d4e5f6a7b8c9
Create Date: 2026-09-02

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = (
    "a1b2c3d4e5f6",
    "d4e5f6a7b8c9",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge the two migration heads."""
    pass


def downgrade() -> None:
    """Merge migration has no schema operations."""
    pass