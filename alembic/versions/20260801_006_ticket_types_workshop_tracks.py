"""add ticket types and workshop tracks

Revision ID: 202608010006
Revises: 202608010005
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa

revision = "202608010006"
down_revision = "202608010005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ticket_types",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("event_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="IDR"),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("sales_start_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("sales_end_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name="fk_ticket_types_event"),
        sa.UniqueConstraint("event_id", "code", name="uq_ticket_types_event_code"),
    )

    op.create_table(
        "workshop_tracks",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("event_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name="fk_workshop_tracks_event"),
    )


def downgrade() -> None:
    op.drop_table("workshop_tracks")
    op.drop_table("ticket_types")

