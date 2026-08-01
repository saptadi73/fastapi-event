"""add participant profile photo

Revision ID: 202608010008
Revises: 202608010007
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa


revision = "202608010008"
down_revision = "202608010007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("participants", sa.Column("profile_photo_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("participants", "profile_photo_url")
