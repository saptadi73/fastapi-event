"""add explicit event-speaker relationship

Revision ID: 202608210025
Revises: 202608200001
"""

from alembic import op
import sqlalchemy as sa


revision = "202608210025"
down_revision = "202608200001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_speakers",
        sa.Column("event_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("speaker_id", sa.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["speaker_id"], ["speakers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id", "speaker_id"),
        sa.UniqueConstraint("event_id", "speaker_id", name="uq_event_speaker"),
    )


def downgrade() -> None:
    op.drop_table("event_speakers")
