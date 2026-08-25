"""organizer assisted matching and meeting reporting

Revision ID: 202608250030
Revises: 202608230029
"""
import sqlalchemy as sa
from alembic import op

revision = "202608250030"
down_revision = "202608230029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizer_match_recommendations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("participant_a_id", sa.Uuid(), nullable=False),
        sa.Column("participant_b_id", sa.Uuid(), nullable=False),
        sa.Column("recommended_by", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(255), nullable=False),
        sa.Column("purpose", sa.String(80), server_default="Organizer assisted matching", nullable=False),
        sa.Column("proposed_slot_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("participant_a_response", sa.String(30), server_default="pending", nullable=False),
        sa.Column("participant_b_response", sa.String(30), server_default="pending", nullable=False),
        sa.Column("participant_a_responded_at", sa.DateTime(timezone=True)),
        sa.Column("participant_b_responded_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(40), server_default="awaiting_responses", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["participant_a_id"], ["participants.id"]),
        sa.ForeignKeyConstraint(["participant_b_id"], ["participants.id"]),
        sa.ForeignKeyConstraint(["recommended_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_match_recommendations_event_status", "organizer_match_recommendations", ["event_id", "status"])
    op.create_index("ix_match_recommendations_participants", "organizer_match_recommendations", ["participant_a_id", "participant_b_id"])
    op.add_column("meetings", sa.Column("source", sa.String(30), server_default="participant_request", nullable=False))
    op.add_column("meetings", sa.Column("organizer_recommendation_id", sa.Uuid()))
    op.create_foreign_key("fk_meeting_organizer_recommendation", "meetings", "organizer_match_recommendations", ["organizer_recommendation_id"], ["id"], ondelete="SET NULL")
    op.create_unique_constraint("uq_meeting_organizer_recommendation", "meetings", ["organizer_recommendation_id"])
    op.create_table(
        "business_matching_event_settings",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("assisted_matching_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("require_mutual_consent", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("auto_create_meeting", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("organizer_override_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("recommendation_expiry_hours", sa.Integer(), server_default="72", nullable=False),
        sa.Column("reminder_hours_before_expiry", sa.Integer(), server_default="24", nullable=False),
        sa.Column("meeting_reminder_hours", sa.JSON(), server_default="[24, 1]", nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("event_id"),
    )


def downgrade() -> None:
    op.drop_table("business_matching_event_settings")
    op.drop_constraint("uq_meeting_organizer_recommendation", "meetings", type_="unique")
    op.drop_constraint("fk_meeting_organizer_recommendation", "meetings", type_="foreignkey")
    op.drop_column("meetings", "organizer_recommendation_id")
    op.drop_column("meetings", "source")
    op.drop_index("ix_match_recommendations_participants", table_name="organizer_match_recommendations")
    op.drop_index("ix_match_recommendations_event_status", table_name="organizer_match_recommendations")
    op.drop_table("organizer_match_recommendations")
