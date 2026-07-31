"""add speakers and event_sessions

Revision ID: 202608010005
Revises: 202608010004
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa

revision = "202608010005"
down_revision = "202608010004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "speakers",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("professional_title", sa.String(length=255), nullable=True),
        sa.Column("organization_name", sa.String(length=255), nullable=True),
        sa.Column("country_code", sa.String(length=3), nullable=True),
        sa.Column("biography", sa.Text(), nullable=True),
        sa.Column("profile_photo_url", sa.Text(), nullable=True),
        sa.Column("linkedin_url", sa.Text(), nullable=True),
        sa.Column("github_url", sa.Text(), nullable=True),
        sa.Column("website_url", sa.Text(), nullable=True),
        sa.Column("expertise_tags", sa.JSON(), nullable=True),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_speakers_users"),
    )

    op.create_table(
        "event_sessions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("event_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("workshop_track_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("session_type", sa.String(length=80), nullable=True),
        sa.Column("room_name", sa.String(length=120), nullable=True),
        sa.Column("start_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("end_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="scheduled"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name="fk_event_sessions_event"),
    )


def downgrade() -> None:
    op.drop_table("event_sessions")
    op.drop_table("speakers")

