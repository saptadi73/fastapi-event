from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_admin
from app.support.responses import success_response
from app.modules.sessions import schemas as session_schemas
from app.modules.sessions.service import SessionService
from app.modules.speakers import schemas as speaker_schemas
from app.modules.speakers.service import SpeakerService
from app.modules.events import schemas
from app.modules.events.service import EventService

router = APIRouter()


@router.get("", summary="List event")
async def list_events(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
):
    items, meta = await EventService.list_events(db, page=page, size=size)
    data = [schemas.EventRead.model_validate(item) for item in items]
    return success_response("List event berhasil diambil", data=data, meta=meta, request=request)


@router.get("/{event_id}", summary="Get event by id")
async def get_event(
    request: Request,
    event_id,
    db: AsyncSession = Depends(get_db_session),
):
    event = await EventService.get_by_id(db, event_id)
    return success_response("Event ditemukan", data=event, request=request)


@router.get("/{slug}/sessions", summary="Get event sessions by slug")
async def get_event_sessions(
    request: Request,
    slug: str,
    db: AsyncSession = Depends(get_db_session),
):
    event = await EventService.get_by_slug(db, slug)
    rows = await SessionService.list_by_event(db, event.id)
    data = [session_schemas.SessionRead.model_validate(row) for row in rows]
    return success_response("Session event ditemukan", data=data, request=request)


@router.get("/{slug}/speakers", summary="Get event speakers by slug")
async def get_event_speakers(
    request: Request,
    slug: str,
    db: AsyncSession = Depends(get_db_session),
):
    event = await EventService.get_by_slug(db, slug)
    speakers = await SpeakerService.list_featured_by_event(db, event.id, size=100)
    data = [speaker_schemas.SpeakerRead.model_validate(row) for row in speakers]
    return success_response("Speaker event ditemukan", data=data, request=request)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create event")
async def create_event(
    request: Request,
    payload: schemas.EventCreate,
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(require_admin),
):
    event = await EventService.create(db, payload)
    return success_response("Event berhasil dibuat", data=schemas.EventRead.model_validate(event), request=request)


@router.put("/{event_id}", summary="Update event")
async def update_event(
    request: Request,
    event_id,
    payload: schemas.EventUpdate,
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(require_admin),
):
    event = await EventService.update(db, event_id, payload)
    return success_response("Event berhasil diperbarui", data=schemas.EventRead.model_validate(event), request=request)
