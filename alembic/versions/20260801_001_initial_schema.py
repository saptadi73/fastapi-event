"""initial schema for core event portal entities

Revision ID: 202608010001
Revises:
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa


revision = "202608010001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "participants",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("organization_name", sa.String(length=255), nullable=True),
        sa.Column("biography", sa.Text(), nullable=True),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("venue_name", sa.String(length=255), nullable=True),
        sa.Column("venue_address", sa.Text(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Asia/Bangkok"),
        sa.Column("start_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("end_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
    )

    op.create_table(
        "registrations",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("event_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("participant_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_type_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("registration_number", sa.String(length=40), nullable=False, unique=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("dietary_preference", sa.String(length=120), nullable=True),
        sa.Column("accessibility_requirements", sa.Text(), nullable=True),
        sa.Column("emergency_contact_name", sa.String(length=255), nullable=True),
        sa.Column("emergency_contact_phone", sa.String(length=40), nullable=True),
        sa.Column("consent_snapshot", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name="fk_reg_event",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["participants.id"],
            name="fk_reg_participant",
        ),
        sa.UniqueConstraint("event_id", "participant_id", name="uq_registration_event_participant"),
    )


def downgrade() -> None:
    op.drop_table("registrations")
    op.drop_table("events")
    op.drop_table("participants")

