from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.modules.participants.models import ParticipantProfile
from app.modules.users.models import User
from . import schemas
from .models import (AuditLog, BusinessMatchingProfile, Conversation, ConversationParticipant,
    MatchingSession, Meeting, MeetingResource, MeetingSlot, MeetingSlotProposal, MeetingStatus,
    Message, MessageType, Notification, ParticipantBlock, ParticipantReport)
from .repository import BusinessMatchingRepository as Repo
from .realtime import conversation_hub


def score_match(source, target):
    """Deterministic MVP scoring; each factor is capped at its documented weight."""
    factors = [
        (set(source.business_needs), set(target.business_offerings), 35, "Offering matches your business need"),
        (set(source.business_interests), set(target.business_interests), 25, "Shared business interest"),
        (set(source.business_sectors), set(target.business_sectors), 15, "Shared industry/sector"),
        (set(source.technology_interests), set(target.technology_interests), 10, "Shared technology interest"),
        (set(source.target_market), set(target.target_market), 10, "Shared target market"),
        (set(source.preferred_regions), {target.country_code} if target.country_code else set(), 5, "Country matches preferred region"),
    ]
    score, reasons = 0, []
    for left, right, weight, label in factors:
        common = left & right
        if common:
            score += weight
            reasons.append(f"{label}: {', '.join(sorted(common))}")
    return score, reasons


class BusinessMatchingService:
    ADMIN_ROLES = {"admin", "organizer"}

    @staticmethod
    async def _admin_user_ids(db: AsyncSession):
        rows = (await db.execute(select(User.id).where(User.role.in_(BusinessMatchingService.ADMIN_ROLES), User.status == "active"))).all()
        return [row[0] for row in rows]

    @staticmethod
    async def _notify(db: AsyncSession, event_id, type: str, title: str, body: str, entity_type: str, entity_id, recipients: list[UUID]):
        if not recipients:
            return
        seen = set()
        for recipient_id in recipients:
            if recipient_id is None or recipient_id in seen:
                continue
            seen.add(recipient_id)
            db.add(Notification(
                user_id=recipient_id,
                event_id=event_id,
                type=type,
                title=title,
                body=body,
                entity_type=entity_type,
                entity_id=entity_id,
            ))

    @staticmethod
    async def _notify_with_admins(
        db: AsyncSession,
        event_id,
        type: str,
        title: str,
        body: str,
        entity_type: str,
        entity_id,
        primary_recipients: list[UUID] | None = None,
    ):
        recipients = list(primary_recipients or [])
        recipients.extend(await BusinessMatchingService._admin_user_ids(db))
        await BusinessMatchingService._notify(db, event_id, type, title, body, entity_type, entity_id, recipients)

    @staticmethod
    async def context(db, user_id, event_id=None):
        participant = await Repo.participant_for_user(db, user_id)
        if not participant: raise HTTPException(403, "Participant profile required")
        if event_id and not await Repo.member(db, event_id, participant.id): raise HTTPException(403, "Confirmed event membership required")
        return participant

    @staticmethod
    async def get_profile(db, user_id, event_id):
        p = await BusinessMatchingService.context(db, user_id, event_id)
        row = await Repo.profile(db, event_id, p.id)
        if not row: raise NotFoundException("BUSINESS_PROFILE_NOT_FOUND", "Profil business matching belum dibuat")
        return row

    @staticmethod
    async def upsert_profile(db, user_id, event_id, payload):
        p = await BusinessMatchingService.context(db, user_id, event_id)
        row = await Repo.profile(db, event_id, p.id)
        if not row:
            row = BusinessMatchingProfile(event_id=event_id, participant_id=p.id)
            db.add(row)
        for key, value in payload.model_dump().items(): setattr(row, key, value)
        await db.commit(); await db.refresh(row)
        return row

    @staticmethod
    async def discover(db, user_id, event_id, filters, recommendations=False):
        me = await BusinessMatchingService.context(db, user_id, event_id)
        mine = await Repo.profile(db, event_id, me.id)
        if not mine or not mine.available_for_matching: raise HTTPException(403, "Business matching is not enabled")
        result = []
        for target, participant in await Repo.discover(db, event_id, me.id, filters):
            # JSON tag filters are kept portable across PostgreSQL and test databases.
            if any(filters.get(k) and filters[k] not in getattr(target, k) for k in ("business_sectors", "business_interests", "technology_interests", "business_offerings", "business_needs", "partnership_types")): continue
            value = schemas.DiscoveryRead.model_validate({**target.__dict__, "full_name": participant.full_name, "profile_photo_url": participant.profile_photo_url})
            if recommendations:
                value.match_score, value.match_reasons = score_match(mine, target)
            result.append(value)
        if recommendations: result.sort(key=lambda x: (-x.match_score, x.full_name))
        return result

    @staticmethod
    async def create_conversation(db, user_id, event_id, payload):
        me = await BusinessMatchingService.context(db, user_id, event_id)
        if me.id == payload.participant_id or not await Repo.member(db, event_id, payload.participant_id): raise ValidationException("INVALID_PARTICIPANT", "Participant tujuan tidak valid")
        target = await Repo.profile(db, event_id, payload.participant_id)
        mine = await Repo.profile(db, event_id, me.id)
        if not mine or not mine.allow_messages or not target or not target.available_for_matching or not target.allow_messages or await Repo.blocked(db, event_id, me.id, target.participant_id): raise HTTPException(403, "Messaging is not allowed")
        existing = await Repo.direct_conversation(db, event_id, me.id, target.participant_id)
        if existing:
            membership = await Repo.conversation_member(db, existing.id, me.id)
            if membership and membership.is_archived:
                membership.is_archived = False
                await db.commit()
            if payload.initial_message:
                await BusinessMatchingService.send_message(db, user_id, existing.id, schemas.MessageCreate(body=payload.initial_message))
            return existing
        conversation = Conversation(event_id=event_id, created_by=me.id)
        db.add(conversation); await db.flush()
        db.add_all([ConversationParticipant(conversation_id=conversation.id, participant_id=me.id), ConversationParticipant(conversation_id=conversation.id, participant_id=target.participant_id)])
        if payload.initial_message:
            db.add(Message(conversation_id=conversation.id, sender_participant_id=me.id, body=payload.initial_message)); conversation.last_message_at = datetime.now(timezone.utc)
            target_user = (await db.execute(select(ParticipantProfile.user_id).where(ParticipantProfile.id == target.participant_id))).scalar_one()
            await BusinessMatchingService._notify_with_admins(
                db,
                event_id=event_id,
                type="new_message",
                title="Pesan baru",
                body="Anda menerima pesan business matching",
                entity_type="conversation",
                entity_id=conversation.id,
                primary_recipients=[target_user],
            )
        await db.commit(); await db.refresh(conversation)
        return conversation

    @staticmethod
    async def require_conversation(db, user_id, conversation_id):
        me = await BusinessMatchingService.context(db, user_id)
        conversation = await Repo.conversation(db, conversation_id)
        if not conversation or not await Repo.conversation_member(db, conversation_id, me.id): raise HTTPException(404, "Conversation not found")
        return me, conversation

    @staticmethod
    async def send_message(db, user_id, conversation_id, payload):
        me, conversation = await BusinessMatchingService.require_conversation(db, user_id, conversation_id)
        if conversation.status != "active": raise ConflictException("CONVERSATION_INACTIVE", "Conversation tidak aktif")
        other = (await db.execute(select(ConversationParticipant.participant_id).where(ConversationParticipant.conversation_id == conversation_id, ConversationParticipant.participant_id != me.id))).scalar_one()
        target = await Repo.profile(db, conversation.event_id, other)
        if not target or not target.allow_messages or await Repo.blocked(db, conversation.event_id, me.id, other): raise HTTPException(403, "Messaging is not allowed")
        if payload.reply_to_message_id:
            replied = await Repo.message(db, payload.reply_to_message_id)
            if not replied or replied.conversation_id != conversation_id or replied.deleted_at is not None:
                raise ValidationException("INVALID_REPLY_MESSAGE", "Pesan yang dibalas tidak valid")
        body = payload.body.strip()
        if not body: raise ValidationException("EMPTY_MESSAGE", "Isi pesan tidak boleh kosong")
        msg = Message(conversation_id=conversation_id, sender_participant_id=me.id, body=body, reply_to_message_id=payload.reply_to_message_id)
        db.add(msg); conversation.last_message_at = datetime.now(timezone.utc)
        user_id_target = (await db.execute(select(ParticipantProfile.user_id).where(ParticipantProfile.id == other))).scalar_one()
        await BusinessMatchingService._notify_with_admins(
            db,
            event_id=conversation.event_id,
            type="new_message",
            title="Pesan baru",
            body="Anda menerima pesan business matching",
            entity_type="conversation",
            entity_id=conversation.id,
            primary_recipients=[user_id_target],
        )
        await db.commit(); await db.refresh(msg)
        await conversation_hub.broadcast(conversation_id, {"type": "new_message", "conversation_id": str(conversation_id), "message": schemas.MessageRead.model_validate(msg).model_dump(mode="json")})
        return msg

    @staticmethod
    async def edit_message(db, user_id, conversation_id, message_id, payload):
        me, _ = await BusinessMatchingService.require_conversation(db, user_id, conversation_id)
        msg = await Repo.message(db, message_id)
        if not msg or msg.conversation_id != conversation_id or msg.deleted_at is not None:
            raise NotFoundException("MESSAGE_NOT_FOUND", "Pesan tidak ditemukan")
        if msg.sender_participant_id != me.id or msg.message_type != MessageType.TEXT:
            raise HTTPException(403, "Only the sender can edit text messages")
        body = payload.body.strip()
        if not body: raise ValidationException("EMPTY_MESSAGE", "Isi pesan tidak boleh kosong")
        msg.body = body; msg.edited_at = datetime.now(timezone.utc)
        await db.commit(); await db.refresh(msg)
        await conversation_hub.broadcast(conversation_id, {"type": "message_updated", "conversation_id": str(conversation_id), "message": schemas.MessageRead.model_validate(msg).model_dump(mode="json")})
        return msg

    @staticmethod
    async def delete_message(db, user_id, conversation_id, message_id):
        me, conversation = await BusinessMatchingService.require_conversation(db, user_id, conversation_id)
        msg = await Repo.message(db, message_id)
        if not msg or msg.conversation_id != conversation_id or msg.deleted_at is not None:
            raise NotFoundException("MESSAGE_NOT_FOUND", "Pesan tidak ditemukan")
        if msg.sender_participant_id != me.id or msg.message_type != MessageType.TEXT:
            raise HTTPException(403, "Only the sender can delete text messages")
        msg.deleted_at = datetime.now(timezone.utc)
        last = (await db.execute(select(Message).where(Message.conversation_id == conversation_id, Message.deleted_at.is_(None), Message.id != msg.id).order_by(Message.created_at.desc()).limit(1))).scalar_one_or_none()
        conversation.last_message_at = last.created_at if last else None
        await db.commit()
        await conversation_hub.broadcast(conversation_id, {"type": "message_deleted", "conversation_id": str(conversation_id), "message_id": str(message_id)})

    @staticmethod
    async def create_meeting(db, user_id, event_id, payload):
        me = await BusinessMatchingService.context(db, user_id, event_id)
        target = await Repo.profile(db, event_id, payload.recipient_participant_id)
        if me.id == payload.recipient_participant_id or not await Repo.member(db, event_id, payload.recipient_participant_id) or not target or not target.allow_meeting_requests or await Repo.blocked(db, event_id, me.id, payload.recipient_participant_id): raise HTTPException(403, "Meeting request is not allowed")
        if payload.conversation_id:
            _, conversation = await BusinessMatchingService.require_conversation(db, user_id, payload.conversation_id)
            recipient_membership = await Repo.conversation_member(db, payload.conversation_id, payload.recipient_participant_id)
            if conversation.event_id != event_id or not recipient_membership:
                raise ValidationException("INVALID_MEETING_CONVERSATION", "Conversation tidak sesuai dengan participant meeting")
        meeting = Meeting(event_id=event_id, requester_participant_id=me.id, recipient_participant_id=payload.recipient_participant_id, conversation_id=payload.conversation_id, purpose=payload.purpose, topic=payload.topic, description=payload.description)
        db.add(meeting); await db.flush()
        for slot_id in payload.proposed_slot_ids: db.add(MeetingSlotProposal(meeting_id=meeting.id, slot_id=slot_id, proposed_by=me.id))
        event_message = await BusinessMatchingService._event(db, meeting, user_id, "meeting_request", "Permintaan meeting", MessageType.MEETING_REQUEST)
        await db.commit(); await db.refresh(meeting)
        if event_message:
            await db.refresh(event_message)
            await conversation_hub.broadcast(event_message.conversation_id, {"type": "new_message", "conversation_id": str(event_message.conversation_id), "message": schemas.MessageRead.model_validate(event_message).model_dump(mode="json")})
        return meeting

    @staticmethod
    async def transition(db, user_id, meeting_id, command, confirm=None):
        me = await BusinessMatchingService.context(db, user_id)
        meeting = await Repo.meeting(db, meeting_id, lock=True)
        if not meeting or me.id not in (meeting.requester_participant_id, meeting.recipient_participant_id): raise HTTPException(404, "Meeting not found")
        allowed = {"accept": ({MeetingStatus.REQUESTED}, MeetingStatus.ACCEPTED), "decline": ({MeetingStatus.REQUESTED}, MeetingStatus.DECLINED), "request-reschedule": ({MeetingStatus.CONFIRMED}, MeetingStatus.RESCHEDULE_REQUESTED), "cancel": ({MeetingStatus.ACCEPTED, MeetingStatus.SCHEDULING, MeetingStatus.CONFIRMED, MeetingStatus.RESCHEDULE_REQUESTED}, MeetingStatus.CANCELLED), "complete": ({MeetingStatus.CONFIRMED}, MeetingStatus.COMPLETED)}
        if command == "confirm":
            if meeting.status not in (MeetingStatus.ACCEPTED, MeetingStatus.SCHEDULING, MeetingStatus.RESCHEDULE_REQUESTED): raise ConflictException("INVALID_MEETING_TRANSITION", "Transisi status meeting tidak valid")
            slot = await db.get(MeetingSlot, confirm.slot_id, with_for_update=True); resource = await db.get(MeetingResource, confirm.resource_id, with_for_update=True)
            if not slot or slot.status != "available" or not resource or not resource.is_active or await Repo.conflict(db, meeting, confirm.slot_id, confirm.resource_id): raise ConflictException("MEETING_SCHEDULE_CONFLICT", "Slot, participant, atau resource sudah digunakan")
            meeting.status = MeetingStatus.CONFIRMED; meeting.confirmed_slot_id = slot.id; meeting.venue_resource_id = resource.id; meeting.confirmed_at = datetime.now(timezone.utc)
        else:
            states, target = allowed[command]
            if meeting.status not in states: raise ConflictException("INVALID_MEETING_TRANSITION", "Transisi status meeting tidak valid")
            if command in ("accept", "decline") and me.id != meeting.recipient_participant_id: raise HTTPException(403, "Only recipient may respond")
            meeting.status = target
            if target == MeetingStatus.CANCELLED: meeting.cancelled_at = datetime.now(timezone.utc)
            if target == MeetingStatus.COMPLETED: meeting.completed_at = datetime.now(timezone.utc)
        event_message = await BusinessMatchingService._event(db, meeting, user_id, f"meeting_{meeting.status.value}", f"Meeting {meeting.status.value}", MessageType.SYSTEM)
        await db.commit(); await db.refresh(meeting)
        if event_message:
            await db.refresh(event_message)
            await conversation_hub.broadcast(event_message.conversation_id, {"type": "meeting_status_update", "conversation_id": str(event_message.conversation_id), "meeting_id": str(meeting.id), "status": meeting.status.value, "message": schemas.MessageRead.model_validate(event_message).model_dump(mode="json")})
        return meeting

    @staticmethod
    async def _event(db, meeting, actor_user_id, event_type, title, message_type):
        recipient_id = meeting.recipient_participant_id if (await Repo.participant_for_user(db, actor_user_id)).id == meeting.requester_participant_id else meeting.requester_participant_id
        target_user = (await db.execute(select(ParticipantProfile.user_id).where(ParticipantProfile.id == recipient_id))).scalar_one()
        await BusinessMatchingService._notify_with_admins(
            db,
            event_id=meeting.event_id,
            type=event_type,
            title=title,
            body=meeting.topic,
            entity_type="meeting",
            entity_id=meeting.id,
            primary_recipients=[target_user],
        )
        db.add(AuditLog(event_id=meeting.event_id, actor_user_id=actor_user_id, action=event_type, entity_type="meeting", entity_id=meeting.id, new_values={"status": meeting.status.value}))
        if meeting.conversation_id:
            message = Message(conversation_id=meeting.conversation_id, sender_participant_id=meeting.requester_participant_id, message_type=message_type, body=title, meeting_id=meeting.id)
            db.add(message)
            conversation = await Repo.conversation(db, meeting.conversation_id)
            if conversation: conversation.last_message_at = datetime.now(timezone.utc)
            return message
        return None
