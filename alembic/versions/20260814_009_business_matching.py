"""business matching MVP

Revision ID: 202608140009
Revises: 202608010008
Create Date: 2026-08-14
"""
from alembic import op
from app.modules.business_matching.models import (
    AuditLog, BusinessMatchingProfile, Conversation, ConversationParticipant,
    MatchingSession, Meeting, MeetingResource, MeetingSlot, MeetingSlotProposal,
    MeetingVenue, Message, Notification, ParticipantBlock, ParticipantReport,
)
from app.modules.iwbif.models import Company

revision = "202608140009"
down_revision = "202608010008"
branch_labels = None
depends_on = None

TABLES = [
    Company.__table__, BusinessMatchingProfile.__table__, ParticipantBlock.__table__, ParticipantReport.__table__, Conversation.__table__,
    ConversationParticipant.__table__, MatchingSession.__table__, MeetingSlot.__table__,
    MeetingVenue.__table__, MeetingResource.__table__, Meeting.__table__, Message.__table__,
    MeetingSlotProposal.__table__, Notification.__table__, AuditLog.__table__,
]

def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind, checkfirst=True)

def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind, checkfirst=True)
