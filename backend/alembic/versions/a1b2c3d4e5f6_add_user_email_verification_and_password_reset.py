"""add user email verification and password reset

Revision ID: a1b2c3d4e5f6
Revises: f5604f7f8fcf
Create Date: 2026-08-29 05:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f5604f7f8fcf'
branch_labels = None
depends_on = None


def upgrade():
    # Add email verification and password reset columns to users table
    # Existing users default to email_verified=True to preserve active test/dev accounts
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('email_otp_hash', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('email_otp_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('email_otp_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('email_otp_last_sent_at', sa.DateTime(timezone=True), nullable=True))

    op.add_column('users', sa.Column('password_reset_token_hash', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('password_reset_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('password_reset_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('password_reset_last_sent_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('users', 'password_reset_last_sent_at')
    op.drop_column('users', 'password_reset_attempts')
    op.drop_column('users', 'password_reset_expires_at')
    op.drop_column('users', 'password_reset_token_hash')

    op.drop_column('users', 'email_otp_last_sent_at')
    op.drop_column('users', 'email_otp_attempts')
    op.drop_column('users', 'email_otp_expires_at')
    op.drop_column('users', 'email_otp_hash')
    op.drop_column('users', 'email_verified_at')
    op.drop_column('users', 'email_verified')
