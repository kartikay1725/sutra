"""add_inline_review_comments_table

Revision ID: 7f9a123b4567
Revises: e9cd867b5905
Create Date: 2026-08-14 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f9a123b4567'
down_revision: Union[str, Sequence[str], None] = 'e9cd867b5905'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'inline_review_comments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('pull_request_id', sa.String(length=36), nullable=False),
        sa.Column('repository_id', sa.String(length=36), nullable=False),
        sa.Column('author_id', sa.String(length=36), nullable=False),
        sa.Column('parent_id', sa.String(length=36), nullable=True),
        sa.Column('path', sa.String(length=1000), nullable=True),
        sa.Column('diff_side', sa.String(length=10), nullable=True),
        sa.Column('line_number', sa.Integer(), nullable=True),
        sa.Column('line_range_start', sa.Integer(), nullable=True),
        sa.Column('line_range_end', sa.Integer(), nullable=True),
        sa.Column('commit_sha', sa.String(length=64), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.String(length=36), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'resolved')",
            name='ck_inline_review_comments_status'
        ),
        sa.CheckConstraint(
            "diff_side IS NULL OR diff_side IN ('LEFT', 'RIGHT')",
            name='ck_inline_review_comments_side'
        ),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['parent_id'], ['inline_review_comments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pull_request_id'], ['pull_requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inline_review_comments_author_id'), 'inline_review_comments', ['author_id'], unique=False)
    op.create_index(op.f('ix_inline_review_comments_parent_id'), 'inline_review_comments', ['parent_id'], unique=False)
    op.create_index(op.f('ix_inline_review_comments_path'), 'inline_review_comments', ['path'], unique=False)
    op.create_index(op.f('ix_inline_review_comments_pull_request_id'), 'inline_review_comments', ['pull_request_id'], unique=False)
    op.create_index(op.f('ix_inline_review_comments_repository_id'), 'inline_review_comments', ['repository_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_inline_review_comments_repository_id'), table_name='inline_review_comments')
    op.drop_index(op.f('ix_inline_review_comments_pull_request_id'), table_name='inline_review_comments')
    op.drop_index(op.f('ix_inline_review_comments_path'), table_name='inline_review_comments')
    op.drop_index(op.f('ix_inline_review_comments_parent_id'), table_name='inline_review_comments')
    op.drop_index(op.f('ix_inline_review_comments_author_id'), table_name='inline_review_comments')
    op.drop_table('inline_review_comments')
