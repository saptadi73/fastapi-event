from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_current_user, get_db_session, require_admin
from app.core.database import AsyncSessionFactory
from app.core.security import decode_token
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.support.responses import success_response
from . import schemas
from .models import ConversationParticipant, MatchingSession, Meeting, MeetingSlot, Notification, ParticipantBlock, ParticipantReport
from .repository import BusinessMatchingRepository as Repo
from .service import BusinessMatchingService as Service
from .realtime import conversation_hub
from app.modules.email_notifications.service import deliver_meeting_update, deliver_to_user
from app.modules.participants.models import ParticipantProfile
from app.modules.events.models import Event

router = APIRouter()

@router.get("/events/{event_id}/business-matching/profile")
async def get_profile(event_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    return success_response("Profil business matching ditemukan", schemas.ProfileRead.model_validate(await Service.get_profile(db, user.id, event_id)), request=request)

@router.put("/events/{event_id}/business-matching/profile")
async def put_profile(event_id: UUID, payload: schemas.ProfileWrite, request: Request, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    row = await Service.upsert_profile(db, user.id, event_id, payload); event = await db.get(Event, event_id)
    background_tasks.add_task(deliver_to_user, event_id, "business_matching_profile_saved", user.id, {"event_name": event.name}, "business_matching_profile", row.id)
    return success_response("Profil business matching berhasil disimpan", schemas.ProfileRead.model_validate(row), request=request)

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
    data = []
    for conversation, membership in rows:
        other, last, unread = await Repo.conversation_summary(db, conversation, membership, me.id)
        if other:
            data.append(schemas.ConversationRead(id=conversation.id, event_id=conversation.event_id, status=conversation.status.value if hasattr(conversation.status, "value") else conversation.status, last_message_at=conversation.last_message_at, unread_count=unread, other_participant_id=other.id, other_participant_name=other.full_name, other_participant_photo_url=other.profile_photo_url, last_message=schemas.MessageRead.model_validate(last) if last else None))
    return success_response("Daftar conversation berhasil diambil", data, request=request)

@router.get("/conversations/{conversation_id}/messages")
async def messages(conversation_id: UUID, request: Request, limit: int = Query(50, ge=1, le=100), before: datetime | None = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    await Service.require_conversation(db, user.id, conversation_id)
    rows = await Repo.messages(db, conversation_id, limit, before)
    return success_response("Daftar pesan berhasil diambil", [schemas.MessageRead.model_validate(x) for x in rows], {"limit": limit, "has_more": len(rows) == limit, "next_before": rows[0].created_at.isoformat() if len(rows) == limit else None}, request)

@router.post("/conversations/{conversation_id}/messages", status_code=201)
async def send_message(conversation_id: UUID, payload: schemas.MessageCreate, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    return success_response("Pesan berhasil dikirim", schemas.MessageRead.model_validate(await Service.send_message(db, user.id, conversation_id, payload)), request=request)

@router.patch("/conversations/{conversation_id}/messages/{message_id}")
async def edit_message(conversation_id: UUID, message_id: UUID, payload: schemas.MessageUpdate, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    return success_response("Pesan berhasil diperbarui", schemas.MessageRead.model_validate(await Service.edit_message(db, user.id, conversation_id, message_id, payload)), request=request)

@router.delete("/conversations/{conversation_id}/messages/{message_id}")
async def delete_message(conversation_id: UUID, message_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    await Service.delete_message(db, user.id, conversation_id, message_id)
    return success_response("Pesan berhasil dihapus", request=request)

@router.get("/messages/unread-count")
async def unread_messages(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    me = await Service.context(db, user.id)
    return success_response("Unread message count berhasil diambil", {"count": await Repo.total_unread_messages(db, me.id)}, request=request)


@router.get("/inbox/unread-count")
async def inbox_unread_count(request: Request, event_id: UUID | None = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    # Notification inbox is available to every authenticated account, including
    # admins/organizers that do not have a participant profile. Chat unread is
    # only applicable when the account is also linked to a participant.
    me = await Repo.participant_for_user(db, user.id)
    messages_unread = await Repo.total_unread_messages(db, me.id) if me else 0
    notifications_unread = await Repo.unread_count(db, user.id, event_id=event_id)
    return success_response(
        "Inbox unread count berhasil diambil",
        schemas.InboxUnreadSummary(
            messages=messages_unread,
            notifications=notifications_unread,
            unread_count=messages_unread + notifications_unread,
        ).model_dump(),
        request=request,
    )

@router.post("/conversations/{conversation_id}/read")
async def read(conversation_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    me, _ = await Service.require_conversation(db, user.id, conversation_id); cp = await Repo.conversation_member(db, conversation_id, me.id)
    cp.last_read_at = datetime.now(timezone.utc); await db.commit()
    await conversation_hub.broadcast(conversation_id, {"type": "read_update", "conversation_id": str(conversation_id), "participant_id": str(me.id), "read_at": cp.last_read_at.isoformat()})
    return success_response("Conversation ditandai sudah dibaca", request=request)

@router.post("/conversations/{conversation_id}/archive")
async def archive(conversation_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    me, _ = await Service.require_conversation(db, user.id, conversation_id); cp = await Repo.conversation_member(db, conversation_id, me.id); cp.is_archived = True; await db.commit()
    return success_response("Conversation berhasil diarsipkan", request=request)

@router.post("/conversations/{conversation_id}/unarchive")
async def unarchive(conversation_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    me, _ = await Service.require_conversation(db, user.id, conversation_id); cp = await Repo.conversation_member(db, conversation_id, me.id); cp.is_archived = False; await db.commit()
    return success_response("Conversation berhasil dikembalikan", request=request)

@router.websocket("/ws/conversations/{conversation_id}")
async def conversation_websocket(websocket: WebSocket, conversation_id: UUID):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401); return
    try:
        payload = decode_token(token)
        if payload.get("type") != "access": raise ValueError("invalid token")
        async with AsyncSessionFactory() as db:
            user = await UserRepository.get_by_id(db, payload.get("sub"))
            if not user: raise ValueError("invalid user")
            await Service.require_conversation(db, user.id, conversation_id)
    except Exception:
        await websocket.close(code=4403); return
    await conversation_hub.connect(conversation_id, websocket)
    try:
        await websocket.send_json({"type": "connected", "conversation_id": str(conversation_id)})
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping": await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await conversation_hub.disconnect(conversation_id, websocket)

@router.post("/events/{event_id}/meetings", status_code=201)
async def create_meeting(event_id: UUID, payload: schemas.MeetingCreate, request: Request, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    actor = await Service.context(db, user.id, event_id); target = await db.get(ParticipantProfile, payload.recipient_participant_id)
    row = await Service.create_meeting(db, user.id, event_id, payload)
    if target:
        background_tasks.add_task(deliver_meeting_update, row.id, "meeting_requested", target.user_id, actor.id)
    return success_response("Meeting request berhasil dibuat", schemas.MeetingRead.model_validate(row), request=request)

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
    async def endpoint(meeting_id: UUID, request: Request, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
        actor = await Service.context(db, user.id); meeting = await Repo.meeting(db, meeting_id)
        target_id = meeting.recipient_participant_id if actor.id == meeting.requester_participant_id else meeting.requester_participant_id
        target = await db.get(ParticipantProfile, target_id)
        row = await Service.transition(db, user.id, meeting_id, command)
        trigger = {"accept": "meeting_accepted", "decline": "meeting_declined", "request-reschedule": "meeting_reschedule_requested", "cancel": "meeting_cancelled"}.get(command)
        if trigger and target:
            background_tasks.add_task(deliver_meeting_update, row.id, trigger, target.user_id, actor.id)
        return success_response("Status meeting berhasil diubah", schemas.MeetingRead.model_validate(row), request=request)
    return endpoint

for _command in ("accept", "decline", "request-reschedule", "cancel", "complete"):
    router.add_api_route(f"/meetings/{{meeting_id}}/{_command}", command_route(_command), methods=["POST"])

@router.post("/meetings/{meeting_id}/confirm")
async def confirm(meeting_id: UUID, payload: schemas.MeetingConfirm, request: Request, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    actor = await Service.context(db, user.id); meeting = await Repo.meeting(db, meeting_id)
    target_id = meeting.recipient_participant_id if actor.id == meeting.requester_participant_id else meeting.requester_participant_id; target = await db.get(ParticipantProfile, target_id)
    row = await Service.transition(db, user.id, meeting_id, "confirm", payload)
    if target:
        background_tasks.add_task(deliver_meeting_update, row.id, "meeting_confirmed", target.user_id, actor.id)
    return success_response("Meeting berhasil dikonfirmasi", schemas.MeetingRead.model_validate(row), request=request)

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
async def notifications(request: Request, event_id: UUID | None = None, request_limit: int = Query(default=100, ge=1, le=200), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    rows = await Repo.notifications(db, user.id, event_id=event_id, limit=request_limit)
    return success_response(
        "Notifikasi berhasil diambil",
        [schemas.NotificationRead.model_validate(x).model_dump(mode="json") for x in rows],
        request=request,
    )

@router.get("/notifications/unread-count")
async def unread(request: Request, event_id: UUID | None = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    return success_response("Unread count berhasil diambil", {"count": await Repo.unread_count(db, user.id, event_id=event_id)}, request=request)

@router.post("/notifications/{notification_id}/read")
async def notification_read(notification_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    from datetime import datetime, timezone
    await db.execute(update(Notification).where(Notification.id == notification_id, Notification.user_id == user.id).values(is_read=True, read_at=datetime.now(timezone.utc))); await db.commit(); return success_response("Notifikasi ditandai dibaca", request=request)

@router.post("/notifications/read-all")
async def read_all(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    from datetime import datetime, timezone
    await db.execute(update(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False)).values(is_read=True, read_at=datetime.now(timezone.utc))); await db.commit(); return success_response("Semua notifikasi ditandai dibaca", request=request)


@router.get("/admin/notifications")
async def admin_notifications(request: Request, event_id: UUID | None = None, request_limit: int = Query(default=100, ge=1, le=200), admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    rows = await Repo.notifications(db, admin.id, event_id=event_id, limit=request_limit)
    return success_response(
        "Notifikasi admin berhasil diambil",
        [schemas.NotificationRead.model_validate(x).model_dump(mode="json") for x in rows],
        request=request,
    )


@router.get("/admin/notifications/unread-count")
async def admin_unread(request: Request, event_id: UUID | None = None, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    return success_response("Unread count admin berhasil diambil", {"count": await Repo.unread_count(db, admin.id, event_id=event_id)}, request=request)


@router.post("/admin/notifications/{notification_id}/read")
async def admin_notification_read(notification_id: UUID, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    await db.execute(update(Notification).where(Notification.id == notification_id, Notification.user_id == admin.id).values(is_read=True, read_at=datetime.now(timezone.utc)))
    await db.commit()
    return success_response("Notifikasi admin ditandai dibaca", request=request)


@router.post("/admin/notifications/read-all")
async def admin_read_all(request: Request, event_id: UUID | None = None, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    q = update(Notification).where(Notification.user_id == admin.id, Notification.is_read.is_(False))
    if event_id is not None:
        q = q.where(Notification.event_id == event_id)
    await db.execute(q.values(is_read=True, read_at=datetime.now(timezone.utc)))
    await db.commit()
    return success_response("Semua notifikasi admin ditandai dibaca", request=request)
