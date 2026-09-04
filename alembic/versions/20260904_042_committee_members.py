"""add event committee members

Revision ID: 202609040042
Revises: 202609030041
"""
from alembic import op
import sqlalchemy as sa


revision = "202609040042"
down_revision = "202609030041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "committee_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role_title", sa.String(length=255), nullable=False),
        sa.Column("committee_group", sa.String(length=160), nullable=True),
        sa.Column("organization_name", sa.String(length=255), nullable=True),
        sa.Column("biography", sa.Text(), nullable=True),
        sa.Column("profile_photo_url", sa.Text(), nullable=True),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_featured", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_committee_members_event_id", "committee_members", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_committee_members_event_id", table_name="committee_members")
    op.drop_table("committee_members")
