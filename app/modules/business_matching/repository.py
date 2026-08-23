from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.participants.models import ParticipantProfile
from app.modules.registrations.models import Registration, RegistrationStatus
from .models import (BusinessMatchingProfile, Conversation, ConversationParticipant, Message,
    Meeting, MeetingResource, MeetingSlot, MeetingVenue, Notification, ParticipantBlock)


class BusinessMatchingRepository:
    @staticmethod
    async def participant_for_user(db: AsyncSession, user_id: UUID):
        return (await db.execute(select(ParticipantProfile).where(ParticipantProfile.user_id == user_id))).scalar_one_or_none()

    @staticmethod
    async def member(db: AsyncSession, event_id: UUID, participant_id: UUID) -> bool:
        return (await db.execute(select(Registration.id).where(Registration.event_id == event_id, Registration.participant_id == participant_id, Registration.status == RegistrationStatus.CONFIRMED))).scalar_one_or_none() is not None

    @staticmethod
    async def profile(db, event_id, participant_id):
        return (await db.execute(select(BusinessMatchingProfile).where(BusinessMatchingProfile.event_id == event_id, BusinessMatchingProfile.participant_id == participant_id))).scalar_one_or_none()

    @staticmethod
    async def blocked(db, event_id, a, b):
        q = select(ParticipantBlock.id).where(ParticipantBlock.event_id == event_id, or_(and_(ParticipantBlock.blocker_id == a, ParticipantBlock.blocked_id == b), and_(ParticipantBlock.blocker_id == b, ParticipantBlock.blocked_id == a)))
        return (await db.execute(q)).first() is not None

    @staticmethod
    async def discover(db, event_id, current_id, filters):
        q = select(BusinessMatchingProfile, ParticipantProfile).join(ParticipantProfile, ParticipantProfile.id == BusinessMatchingProfile.participant_id).join(Registration, and_(Registration.event_id == event_id, Registration.participant_id == BusinessMatchingProfile.participant_id, Registration.status == RegistrationStatus.CONFIRMED)).where(BusinessMatchingProfile.event_id == event_id, BusinessMatchingProfile.participant_id != current_id, BusinessMatchingProfile.available_for_matching.is_(True), BusinessMatchingProfile.visibility != "hidden", ~BusinessMatchingProfile.participant_id.in_(select(ParticipantBlock.blocked_id).where(ParticipantBlock.event_id == event_id, ParticipantBlock.blocker_id == current_id)), ~BusinessMatchingProfile.participant_id.in_(select(ParticipantBlock.blocker_id).where(ParticipantBlock.event_id == event_id, ParticipantBlock.blocked_id == current_id)))
        for key in ("country_code", "organization_type"):
            if filters.get(key): q = q.where(getattr(BusinessMatchingProfile, key) == filters[key])
        return list((await db.execute(q.order_by(ParticipantProfile.full_name))).all())

    @staticmethod
    async def conversation_member(db, conversation_id, participant_id):
        return (await db.execute(select(ConversationParticipant).where(ConversationParticipant.conversation_id == conversation_id, ConversationParticipant.participant_id == participant_id))).scalar_one_or_none()

    @staticmethod
    async def conversation(db, conversation_id): return await db.get(Conversation, conversation_id)

    @staticmethod
    async def conversations(db, event_id, participant_id):
        q = select(Conversation, ConversationParticipant).join(ConversationParticipant).where(Conversation.event_id == event_id, ConversationParticipant.participant_id == participant_id, ConversationParticipant.is_archived.is_(False)).order_by(Conversation.last_message_at.desc().nullslast())
        return list((await db.execute(q)).all())

    @staticmethod
    async def direct_conversation(db, event_id, first_id, second_id):
        mine = aliased(ConversationParticipant)
        other = aliased(ConversationParticipant)
        q = (select(Conversation).join(mine, mine.conversation_id == Conversation.id).join(other, other.conversation_id == Conversation.id).where(Conversation.event_id == event_id, mine.participant_id == first_id, other.participant_id == second_id, Conversation.status == "active"))
        return (await db.execute(q)).scalars().first()

    @staticmethod
    async def messages(db, conversation_id, limit=50, before=None):
        q = select(Message).where(Message.conversation_id == conversation_id, Message.deleted_at.is_(None))
        if before is not None: q = q.where(Message.created_at < before)
        rows = list((await db.execute(q.order_by(Message.created_at.desc()).limit(limit))).scalars())
        rows.reverse()
        return rows

    @staticmethod
    async def message(db, message_id):
        return await db.get(Message, message_id)

    @staticmethod
    async def conversation_summary(db, conversation, membership, participant_id):
        other = (await db.execute(select(ParticipantProfile).join(ConversationParticipant, ConversationParticipant.participant_id == ParticipantProfile.id).where(ConversationParticipant.conversation_id == conversation.id, ConversationParticipant.participant_id != participant_id))).scalars().first()
        last = (await db.execute(select(Message).where(Message.conversation_id == conversation.id, Message.deleted_at.is_(None)).order_by(Message.created_at.desc()).limit(1))).scalar_one_or_none()
        unread_q = select(func.count()).select_from(Message).where(Message.conversation_id == conversation.id, Message.deleted_at.is_(None), Message.sender_participant_id != participant_id)
        if membership.last_read_at is not None: unread_q = unread_q.where(Message.created_at > membership.last_read_at)
        unread = (await db.execute(unread_q)).scalar_one()
        return other, last, unread

    @staticmethod
    async def total_unread_messages(db, participant_id):
        cp = aliased(ConversationParticipant)
        q = select(func.count()).select_from(Message).join(cp, cp.conversation_id == Message.conversation_id).where(cp.participant_id == participant_id, cp.is_archived.is_(False), Message.deleted_at.is_(None), Message.sender_participant_id != participant_id, or_(cp.last_read_at.is_(None), Message.created_at > cp.last_read_at))
        return (await db.execute(q)).scalar_one()

    @staticmethod
    async def meeting(db, meeting_id, lock=False):
        q = select(Meeting).where(Meeting.id == meeting_id)
        if lock: q = q.with_for_update()
        return (await db.execute(q)).scalar_one_or_none()

    @staticmethod
    async def meetings(db, event_id, participant_id):
        q = select(Meeting).where(Meeting.event_id == event_id, or_(Meeting.requester_participant_id == participant_id, Meeting.recipient_participant_id == participant_id)).order_by(Meeting.created_at.desc())
        return list((await db.execute(q)).scalars())

    @staticmethod
    async def conflict(db, meeting, slot_id, resource_id):
        q = select(Meeting.id).where(Meeting.id != meeting.id, Meeting.status == "confirmed", Meeting.confirmed_slot_id == slot_id, or_(Meeting.venue_resource_id == resource_id, Meeting.requester_participant_id.in_([meeting.requester_participant_id, meeting.recipient_participant_id]), Meeting.recipient_participant_id.in_([meeting.requester_participant_id, meeting.recipient_participant_id]))).with_for_update()
        return (await db.execute(q)).first() is not None

    @staticmethod
    async def resources(db, event_id):
        return list((await db.execute(select(MeetingResource).join(MeetingVenue).where(MeetingVenue.event_id == event_id, MeetingResource.is_active.is_(True)))).scalars())

    @staticmethod
    async def notifications(db, user_id, event_id=None, limit: int = 100):
        q = select(Notification).where(Notification.user_id == user_id)
        if event_id is not None:
            q = q.where(Notification.event_id == event_id)
        return list((await db.execute(q.order_by(Notification.created_at.desc()).limit(limit))).scalars())

    @staticmethod
    async def unread_count(db, user_id, event_id=None):
        q = select(func.count()).select_from(Notification).where(Notification.user_id == user_id, Notification.is_read.is_(False))
        if event_id is not None:
            q = q.where(Notification.event_id == event_id)
        return (await db.execute(q)).scalar_one()
