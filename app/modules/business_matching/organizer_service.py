from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.exceptions import ConflictException
from app.modules.participants.models import ParticipantProfile
from app.modules.events.models import Event
from . import schemas
from .models import (AuditLog, BusinessMatchingEventSettings, Meeting, MeetingResource, MeetingSlot, MeetingStatus,
    Notification, OrganizerMatchRecommendation, RecommendationResponse,
    RecommendationStatus)
from .repository import BusinessMatchingRepository as Repo


class OrganizerMatchingService:
    @staticmethod
    async def create_recommendation(db: AsyncSession, event_id, actor, payload):
        settings = await db.get(BusinessMatchingEventSettings, event_id)
        if settings and not settings.assisted_matching_enabled:
            raise HTTPException(409, "Organizer assisted matching is disabled for this event")
        if payload.participant_a_id == payload.participant_b_id:
            raise HTTPException(400, "Recommendation requires two different participants")
        for participant_id in (payload.participant_a_id, payload.participant_b_id):
            if not await Repo.member(db, event_id, participant_id):
                raise HTTPException(400, "Both participants must be confirmed event members")
        if await Repo.blocked(db, event_id, payload.participant_a_id, payload.participant_b_id):
            raise HTTPException(409, "Blocked participants cannot be matched")
        values = payload.model_dump()
        if values["expires_at"] is None:
            values["expires_at"] = datetime.now(timezone.utc) + timedelta(hours=settings.recommendation_expiry_hours if settings else 72)
        row = OrganizerMatchRecommendation(event_id=event_id, recommended_by=actor.id, **values)
        db.add(row)
        await db.flush()
        participants = list((await db.execute(select(ParticipantProfile).where(ParticipantProfile.id.in_([payload.participant_a_id, payload.participant_b_id])))).scalars())
        for participant in participants:
            db.add(Notification(user_id=participant.user_id, event_id=event_id, type="organizer_recommendation", title="Usulan business matching baru", body=payload.topic, entity_type="organizer_recommendation", entity_id=row.id))
        db.add(AuditLog(event_id=event_id, actor_user_id=actor.id, action="organizer_recommendation_created", entity_type="organizer_recommendation", entity_id=row.id, new_values={"participant_a_id": str(payload.participant_a_id), "participant_b_id": str(payload.participant_b_id), "status": row.status.value}))
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def respond(db: AsyncSession, recommendation_id, user_id, response):
        participant = await Repo.participant_for_user(db, user_id)
        row = await db.get(OrganizerMatchRecommendation, recommendation_id, with_for_update=True)
        if not participant or not row or participant.id not in (row.participant_a_id, row.participant_b_id):
            raise HTTPException(404, "Recommendation not found")
        if row.status not in (RecommendationStatus.PROPOSED, RecommendationStatus.AWAITING_RESPONSES):
            raise ConflictException("RECOMMENDATION_CLOSED", "Recommendation is no longer open")
        if row.expires_at and row.expires_at <= datetime.now(timezone.utc):
            row.status = RecommendationStatus.EXPIRED
            await db.commit()
            raise ConflictException("RECOMMENDATION_EXPIRED", "Recommendation has expired")
        now = datetime.now(timezone.utc)
        if participant.id == row.participant_a_id:
            row.participant_a_response, row.participant_a_responded_at = response, now
        else:
            row.participant_b_response, row.participant_b_responded_at = response, now
        responses = {row.participant_a_response, row.participant_b_response}
        meeting = None
        if RecommendationResponse.NOT_INTERESTED in responses:
            row.status = RecommendationStatus.DECLINED
        elif responses == {RecommendationResponse.INTERESTED}:
            row.status = RecommendationStatus.MUTUALLY_INTERESTED
            settings = await db.get(BusinessMatchingEventSettings, row.event_id)
            if not settings or settings.auto_create_meeting:
                meeting = Meeting(event_id=row.event_id, requester_participant_id=row.participant_a_id, recipient_participant_id=row.participant_b_id, purpose=row.purpose, topic=row.topic, description=row.reason, status=MeetingStatus.SCHEDULING, source="organizer_recommendation", organizer_recommendation_id=row.id)
                db.add(meeting)
                await db.flush()
                row.status = RecommendationStatus.CONVERTED_TO_MEETING
        db.add(AuditLog(event_id=row.event_id, actor_user_id=user_id, action="organizer_recommendation_response", entity_type="organizer_recommendation", entity_id=row.id, new_values={"response": response.value, "status": row.status.value, "meeting_id": str(meeting.id) if meeting else None}))
        await db.commit()
        await db.refresh(row)
        return row, meeting

    @staticmethod
    async def participant_recommendations(db: AsyncSession, event_id, user_id):
        participant = await Repo.participant_for_user(db, user_id)
        if not participant or not await Repo.member(db, event_id, participant.id):
            raise HTTPException(403, "Confirmed event membership required")
        q = select(OrganizerMatchRecommendation).where(OrganizerMatchRecommendation.event_id == event_id, or_(OrganizerMatchRecommendation.participant_a_id == participant.id, OrganizerMatchRecommendation.participant_b_id == participant.id)).order_by(OrganizerMatchRecommendation.created_at.desc())
        return list((await db.execute(q)).scalars())

    @staticmethod
    async def recommendations(db: AsyncSession, event_id, status_filter=None):
        q = select(OrganizerMatchRecommendation).where(OrganizerMatchRecommendation.event_id == event_id)
        if status_filter:
            q = q.where(OrganizerMatchRecommendation.status == status_filter)
        return list((await db.execute(q.order_by(OrganizerMatchRecommendation.created_at.desc()))).scalars())

    @staticmethod
    async def meeting_report(db: AsyncSession, event_id, status_filter=None, source=None, search=None, page=1, size=20):
        requester, recipient = aliased(ParticipantProfile), aliased(ParticipantProfile)
        base = select(Meeting, requester, recipient).join(requester, requester.id == Meeting.requester_participant_id).join(recipient, recipient.id == Meeting.recipient_participant_id).where(Meeting.event_id == event_id)
        if status_filter:
            base = base.where(Meeting.status == status_filter)
        if source:
            base = base.where(Meeting.source == source)
        if search:
            pattern = f"%{search}%"
            base = base.where(or_(requester.full_name.ilike(pattern), recipient.full_name.ilike(pattern), requester.organization_name.ilike(pattern), recipient.organization_name.ilike(pattern), Meeting.topic.ilike(pattern)))
        total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        rows = (await db.execute(base.order_by(Meeting.created_at.desc()).offset((page - 1) * size).limit(size))).all()
        counts = dict((await db.execute(select(Meeting.status, func.count()).where(Meeting.event_id == event_id).group_by(Meeting.status))).all())
        summary = {status.value: counts.get(status, counts.get(status.value, 0)) for status in MeetingStatus}
        summary["total"] = sum(summary.values())
        summary["needs_attention"] = summary["requested"] + summary["accepted"] + summary["scheduling"] + summary["reschedule_requested"]
        items = []
        for meeting, a, b in rows:
            items.append({"meeting": schemas.MeetingRead.model_validate(meeting).model_dump(mode="json"), "requester": {"id": a.id, "name": a.full_name, "organization": a.organization_name}, "recipient": {"id": b.id, "name": b.full_name, "organization": b.organization_name}})
        return {"summary": summary, "items": items, "pagination": {"page": page, "size": size, "total": total, "pages": (total + size - 1) // size}}

    @staticmethod
    async def operate_meeting(db: AsyncSession, meeting_id, actor, payload):
        meeting = await Repo.meeting(db, meeting_id, lock=True)
        if not meeting:
            raise HTTPException(404, "Meeting not found")
        settings = await db.get(BusinessMatchingEventSettings, meeting.event_id)
        if settings and not settings.organizer_override_enabled:
            raise HTTPException(409, "Organizer meeting override is disabled for this event")
        old_status = meeting.status.value
        now = datetime.now(timezone.utc)
        if payload.action == "confirm":
            if meeting.status not in (MeetingStatus.REQUESTED, MeetingStatus.ACCEPTED, MeetingStatus.SCHEDULING, MeetingStatus.RESCHEDULE_REQUESTED):
                raise ConflictException("INVALID_MEETING_TRANSITION", "Meeting cannot be confirmed from its current status")
            if not payload.slot_id or not payload.resource_id:
                raise HTTPException(422, "slot_id and resource_id are required for confirmation")
            slot = await db.get(MeetingSlot, payload.slot_id, with_for_update=True)
            resource = await db.get(MeetingResource, payload.resource_id, with_for_update=True)
            if not slot or slot.status != "available" or not resource or not resource.is_active or await Repo.conflict(db, meeting, payload.slot_id, payload.resource_id):
                raise ConflictException("MEETING_SCHEDULE_CONFLICT", "Slot, participant, or resource is unavailable")
            meeting.status, meeting.confirmed_slot_id, meeting.venue_resource_id, meeting.confirmed_at = MeetingStatus.CONFIRMED, slot.id, resource.id, now
        elif payload.action == "cancel":
            if meeting.status in (MeetingStatus.CANCELLED, MeetingStatus.COMPLETED, MeetingStatus.DECLINED, MeetingStatus.NO_SHOW):
                raise ConflictException("INVALID_MEETING_TRANSITION", "Meeting is already closed")
            meeting.status, meeting.cancelled_at = MeetingStatus.CANCELLED, now
        elif payload.action == "complete":
            if meeting.status != MeetingStatus.CONFIRMED:
                raise ConflictException("INVALID_MEETING_TRANSITION", "Only a confirmed meeting can be completed")
            meeting.status, meeting.completed_at = MeetingStatus.COMPLETED, now
        else:
            if meeting.status != MeetingStatus.CONFIRMED:
                raise ConflictException("INVALID_MEETING_TRANSITION", "Only a confirmed meeting can be marked no-show")
            meeting.status = MeetingStatus.NO_SHOW
        db.add(AuditLog(event_id=meeting.event_id, actor_user_id=actor.id, action=f"organizer_meeting_{payload.action}", entity_type="meeting", entity_id=meeting.id, old_values={"status": old_status}, new_values={"status": meeting.status.value, "reason": payload.reason, "slot_id": str(payload.slot_id) if payload.slot_id else None, "resource_id": str(payload.resource_id) if payload.resource_id else None}))
        participant_rows = list((await db.execute(select(ParticipantProfile).where(ParticipantProfile.id.in_([meeting.requester_participant_id, meeting.recipient_participant_id])))).scalars())
        for participant in participant_rows:
            db.add(Notification(user_id=participant.user_id, event_id=meeting.event_id, type=f"meeting_{meeting.status.value}", title="Meeting diperbarui organizer", body=f"{meeting.topic}: {payload.reason}", entity_type="meeting", entity_id=meeting.id))
        await db.commit()
        await db.refresh(meeting)
        return meeting

    @staticmethod
    async def update_settings(db: AsyncSession, event_id, actor, payload):
        if await db.get(Event, event_id) is None:
            raise HTTPException(404, "Event not found")
        row = await db.get(BusinessMatchingEventSettings, event_id)
        values = payload.model_dump()
        if row is None:
            row = BusinessMatchingEventSettings(event_id=event_id, updated_by=actor.id, **values)
            db.add(row)
        else:
            for key, value in values.items():
                setattr(row, key, value)
            row.updated_by = actor.id
        db.add(AuditLog(event_id=event_id, actor_user_id=actor.id, action="business_matching_settings_updated", entity_type="business_matching_settings", entity_id=event_id, new_values=values))
        await db.commit()
        await db.refresh(row)
        return row
