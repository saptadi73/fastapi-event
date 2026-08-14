"""remove ASEAN AI workshop and developer-pass legacy

Revision ID: 202608140011
Revises: 202608140010
Create Date: 2026-08-14
"""
from alembic import op
import sqlalchemy as sa

revision = "202608140011"
down_revision = "202608140010"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.drop_column("event_sessions", "workshop_track_id")
    op.drop_column("registrations", "ticket_type_id")
    op.drop_column("speakers", "github_url")
    op.drop_table("workshop_tracks")
    op.drop_table("ticket_types")
    op.alter_column("events", "timezone", server_default="Asia/Jakarta")

def downgrade() -> None:
    op.create_table("ticket_types", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id"), nullable=False), sa.Column("code", sa.String(40), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("description", sa.Text()), sa.Column("price", sa.Numeric(18, 2), nullable=False), sa.Column("currency", sa.String(3), nullable=False), sa.Column("capacity", sa.Integer(), nullable=False), sa.Column("sales_start_at", sa.DateTime(timezone=True)), sa.Column("sales_end_at", sa.DateTime(timezone=True)), sa.Column("is_active", sa.Boolean(), nullable=False))
    op.create_table("workshop_tracks", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id"), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("description", sa.Text()), sa.Column("capacity", sa.Integer(), nullable=False), sa.Column("order_index", sa.Integer(), nullable=False))
    op.add_column("speakers", sa.Column("github_url", sa.Text()))
    op.add_column("registrations", sa.Column("ticket_type_id", sa.Uuid()))
    op.add_column("event_sessions", sa.Column("workshop_track_id", sa.Uuid()))
    op.alter_column("events", "timezone", server_default="Asia/Bangkok")
