"""add payment channel catalog

Revision ID: 202608170015
Revises: 202608170014
"""
from alembic import op
import sqlalchemy as sa

revision = "202608170015"
down_revision = "202608170014"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("payment_channels",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False), sa.Column("code", sa.String(60), nullable=False), sa.Column("category", sa.String(30), nullable=False), sa.Column("display_name", sa.String(100), nullable=False), sa.Column("logo_url", sa.Text(), nullable=True), sa.Column("config_key", sa.String(100), nullable=True), sa.Column("merchant_id", sa.String(128), nullable=True), sa.Column("sub_merchant_id", sa.String(128), nullable=True), sa.Column("terminal_id", sa.String(128), nullable=True), sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("provider", "code", name="uq_payment_channel_provider_code"))

def downgrade() -> None:
    op.drop_table("payment_channels")
