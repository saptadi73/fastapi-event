from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_session, require_admin
from app.modules.sessions import schemas
from app.modules.sessions.service import SessionService
from app.support.responses import success_response

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/events/{event_id}", summary="List sessions by event")
async def list_sessions(
    request: Request,
    event_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    rows = await SessionService.list_by_event(db, event_id)
    data = [schemas.SessionRead.model_validate(row) for row in rows]
    return success_response("List sesi berhasil", data=data, request=request)


@router.get("/{session_id}", summary="Get session")
async def get_session(
    request: Request,
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    data = await SessionService.get(db, session_id)
    return success_response("Session ditemukan", data=data, request=request)


@router.post("", summary="Create session")
async def create_session(
    request: Request,
    payload: schemas.SessionCreate,
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(require_admin),
):
    data = await SessionService.create(db, payload)
    return success_response("Session berhasil dibuat", data=data, request=request)


@router.put("/{session_id}", summary="Update session")
async def update_session(
    request: Request,
    session_id: UUID,
    payload: schemas.SessionUpdate,
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(require_admin),
):
    data = await SessionService.update(db, session_id, payload)
    return success_response("Session berhasil diubah", data=data, request=request)
