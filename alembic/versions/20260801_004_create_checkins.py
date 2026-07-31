"""create check_ins table

Revision ID: 202608010004
Revises: 202608010003
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa

revision = "202608010004"
down_revision = "202608010003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "check_ins",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("check_in_type", sa.String(length=20), nullable=False, server_default="qr"),
        sa.Column("check_in_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("check_in_by", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("gate_name", sa.String(length=120), nullable=True),
        sa.Column("device_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="success"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], name="fk_checkins_ticket"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name="fk_checkins_event"),
        sa.ForeignKeyConstraint(["check_in_by"], ["users.id"], name="fk_checkins_user"),
    )


def downgrade() -> None:
    op.drop_table("check_ins")

