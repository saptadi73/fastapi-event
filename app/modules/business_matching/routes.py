from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_current_user, get_db_session
from app.modules.users.models import User
from app.support.responses import success_response
from . import schemas
from .models import ConversationParticipant, MatchingSession, Meeting, MeetingSlot, Notification, ParticipantBlock, ParticipantReport
from .repository import BusinessMatchingRepository as Repo
from .service import BusinessMatchingService as Service

router = APIRouter()

@router.get("/events/{event_id}/business-matching/profile")
async def get_profile(event_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    return success_response("Profil business matching ditemukan", schemas.ProfileRead.model_validate(await Service.get_profile(db, user.id, event_id)), request=request)

@router.put("/events/{event_id}/business-matching/profile")
async def put_profile(event_id: UUID, payload: schemas.ProfileWrite, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    return success_response("Profil business matching berhasil disimpan", schemas.ProfileRead.model_validate(await Service.upsert_profile(db, user.id, event_id, payload)), request=request)

async def _discover(event_id, user, db, recommendations, **filters): return await Service.discover(db, user.id, event_id, filters, recommendations)

@router.get("/events/{event_id}/business-matching/participants")
async def participants(event_id: UUID, request: Request, country: str | None = None, organization_type: str | None = None, sector: str | None = None, business_interest: str | None = None, technology_interest: str | None = None, offering: str | None = None, looking_for: str | None = None, partnership_type: str | None = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    data = await _discover(event_id, user, db, False, country_code=country.upper() if country else None, organization_type=organization_type, business_sectors=sector, business_interests=business_interest, technology_interests=technology_interest, business_offerings=offering, business_needs=looking_for, partnership_types=partnership_type)
    return success_response("Daftar participant berhasil diambil", data, {"total": len(data)}, request)

@router.get("/events/{event_id}/business-matching/recommendations")
async def recommendations(event_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    data = await _discover(event_id, user, db, True)
    return success_response("Rekomendasi berhasil dihitung", data, {"total": len(data)}, request)

@router.post("/events/{event_id}/conversations", status_code=201)
async def create_conversation(event_id: UUID, payload: schemas.ConversationCreate, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    row = await Service.create_conversation(db, user.id, event_id, payload)
    return success_response("Conversation berhasil dibuat", {"id": row.id, "status": row.status}, request=request)

@router.get("/events/{event_id}/conversations")
async def conversations(event_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    me = await Service.context(db, user.id, event_id); rows = await Repo.conversations(db, event_id, me.id)
    data = [{"id": c.id, "status": c.status, "last_message_at": c.last_message_at, "unread_count": len([m for m in await Repo.messages(db, c.id) if cp.last_read_at is None or m.created_at > cp.last_read_at])} for c, cp in rows]
    return success_response("Daftar conversation berhasil diambil", data, request=request)

@router.get("/conversations/{conversation_id}/messages")
async def messages(conversation_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    await Service.require_conversation(db, user.id, conversation_id)
    return success_response("Daftar pesan berhasil diambil", [schemas.MessageRead.model_validate(x) for x in await Repo.messages(db, conversation_id)], request=request)

@router.post("/conversations/{conversation_id}/messages", status_code=201)
async def send_message(conversation_id: UUID, payload: schemas.MessageCreate, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    return success_response("Pesan berhasil dikirim", schemas.MessageRead.model_validate(await Service.send_message(db, user.id, conversation_id, payload)), request=request)

@router.post("/conversations/{conversation_id}/read")
async def read(conversation_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    me, _ = await Service.require_conversation(db, user.id, conversation_id); cp = await Repo.conversation_member(db, conversation_id, me.id)
    from datetime import datetime, timezone
    cp.last_read_at = datetime.now(timezone.utc); await db.commit()
    return success_response("Conversation ditandai sudah dibaca", request=request)

@router.post("/conversations/{conversation_id}/archive")
async def archive(conversation_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    me, _ = await Service.require_conversation(db, user.id, conversation_id); cp = await Repo.conversation_member(db, conversation_id, me.id); cp.is_archived = True; await db.commit()
    return success_response("Conversation berhasil diarsipkan", request=request)

@router.post("/events/{event_id}/meetings", status_code=201)
async def create_meeting(event_id: UUID, payload: schemas.MeetingCreate, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    return success_response("Meeting request berhasil dibuat", schemas.MeetingRead.model_validate(await Service.create_meeting(db, user.id, event_id, payload)), request=request)

@router.get("/events/{event_id}/meetings")
async def meetings(event_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    me = await Service.context(db, user.id, event_id); return success_response("Daftar meeting berhasil diambil", [schemas.MeetingRead.model_validate(x) for x in await Repo.meetings(db, event_id, me.id)], request=request)

@router.get("/meetings/{meeting_id}")
async def meeting(meeting_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    me = await Service.context(db, user.id); row = await Repo.meeting(db, meeting_id)
    if not row or me.id not in (row.requester_participant_id, row.recipient_participant_id):
        from fastapi import HTTPException
        raise HTTPException(404, "Meeting not found")
    return success_response("Meeting ditemukan", schemas.MeetingRead.model_validate(row), request=request)

def command_route(command):
    async def endpoint(meeting_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
        return success_response("Status meeting berhasil diubah", schemas.MeetingRead.model_validate(await Service.transition(db, user.id, meeting_id, command)), request=request)
    return endpoint

for _command in ("accept", "decline", "request-reschedule", "cancel", "complete"):
    router.add_api_route(f"/meetings/{{meeting_id}}/{_command}", command_route(_command), methods=["POST"])

@router.post("/meetings/{meeting_id}/confirm")
async def confirm(meeting_id: UUID, payload: schemas.MeetingConfirm, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    return success_response("Meeting berhasil dikonfirmasi", schemas.MeetingRead.model_validate(await Service.transition(db, user.id, meeting_id, "confirm", payload)), request=request)

@router.get("/events/{event_id}/matching-sessions")
async def sessions(event_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    await Service.context(db, user.id, event_id); rows = list((await db.execute(select(MatchingSession).where(MatchingSession.event_id == event_id))).scalars()); return success_response("Matching sessions berhasil diambil", rows, request=request)

@router.get("/events/{event_id}/meeting-slots")
async def slots(event_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    await Service.context(db, user.id, event_id); rows = list((await db.execute(select(MeetingSlot).join(MatchingSession).where(MatchingSession.event_id == event_id, MeetingSlot.status == "available"))).scalars()); return success_response("Meeting slots berhasil diambil", rows, request=request)

@router.get("/events/{event_id}/meeting-resources")
async def resources(event_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    await Service.context(db, user.id, event_id); return success_response("Meeting resources berhasil diambil", await Repo.resources(db, event_id), request=request)

@router.get("/events/{event_id}/availability")
async def availability(event_id: UUID, request: Request, participant_id: UUID | None = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    me = await Service.context(db, user.id, event_id); subject = participant_id or me.id
    if subject != me.id: raise HTTPException(403, "Only your own availability may be viewed")
    rows = list((await db.execute(select(Meeting.confirmed_slot_id).where(Meeting.event_id == event_id, Meeting.status == "confirmed", (Meeting.requester_participant_id == subject) | (Meeting.recipient_participant_id == subject)))).scalars())
    return success_response("Availability berhasil diambil", {"participant_id": subject, "occupied_slot_ids": [x for x in rows if x]}, request=request)

@router.post("/events/{event_id}/business-matching/block", status_code=201)
async def block(event_id: UUID, payload: schemas.ParticipantModeration, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    me = await Service.context(db, user.id, event_id)
    if me.id == payload.participant_id or not await Repo.member(db, event_id, payload.participant_id): raise HTTPException(400, "Invalid participant")
    if not await Repo.blocked(db, event_id, me.id, payload.participant_id): db.add(ParticipantBlock(event_id=event_id, blocker_id=me.id, blocked_id=payload.participant_id)); await db.commit()
    return success_response("Participant berhasil diblokir", request=request)

@router.delete("/events/{event_id}/business-matching/block/{participant_id}")
async def unblock(event_id: UUID, participant_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    me = await Service.context(db, user.id, event_id)
    from .models import ParticipantBlock
    row = (await db.execute(select(ParticipantBlock).where(ParticipantBlock.event_id == event_id, ParticipantBlock.blocker_id == me.id, ParticipantBlock.blocked_id == participant_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Block relation not found")
    await db.delete(row); await db.commit(); return success_response("Blokir participant berhasil dibuka", request=request)

@router.post("/events/{event_id}/business-matching/report", status_code=201)
async def report(event_id: UUID, payload: schemas.ParticipantModeration, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    me = await Service.context(db, user.id, event_id)
    if me.id == payload.participant_id or not payload.reason: raise HTTPException(400, "Participant and reason are required")
    row = ParticipantReport(event_id=event_id, reporter_id=me.id, reported_id=payload.participant_id, reason=payload.reason, details=payload.details); db.add(row); await db.commit(); await db.refresh(row)
    return success_response("Laporan participant berhasil dibuat", {"id": row.id, "status": row.status}, request=request)

@router.get("/notifications")
async def notifications(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)): return success_response("Notifikasi berhasil diambil", await Repo.notifications(db, user.id), request=request)

@router.get("/notifications/unread-count")
async def unread(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)): return success_response("Unread count berhasil diambil", {"count": await Repo.unread_count(db, user.id)}, request=request)

@router.post("/notifications/{notification_id}/read")
async def notification_read(notification_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    from datetime import datetime, timezone
    await db.execute(update(Notification).where(Notification.id == notification_id, Notification.user_id == user.id).values(is_read=True, read_at=datetime.now(timezone.utc))); await db.commit(); return success_response("Notifikasi ditandai dibaca", request=request)

@router.post("/notifications/read-all")
async def read_all(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    from datetime import datetime, timezone
    await db.execute(update(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False)).values(is_read=True, read_at=datetime.now(timezone.utc))); await db.commit(); return success_response("Semua notifikasi ditandai dibaca", request=request)
