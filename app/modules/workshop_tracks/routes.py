from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_session
from app.modules.workshop_tracks import schemas
from app.modules.workshop_tracks.service import WorkshopTrackService
from app.support.responses import success_response

router = APIRouter(prefix="/workshop-tracks", tags=["workshop-tracks"])


@router.get("/events/{event_id}", summary="List workshop tracks by event")
async def list_tracks(
    request: Request,
    event_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    rows = await WorkshopTrackService.list_by_event(db, event_id)
    return success_response("List track", data=rows, request=request)


@router.get("/{track_id}", summary="Get track")
async def get_track(
    request: Request,
    track_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    data = await WorkshopTrackService.get(db, track_id)
    return success_response("Track ditemukan", data=data, request=request)


@router.post("", summary="Create track")
async def create_track(
    request: Request,
    payload: schemas.WorkshopTrackCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    data = await WorkshopTrackService.create(db, payload)
    return success_response("Track berhasil dibuat", data=data, request=request)


@router.put("/{track_id}", summary="Update track")
async def update_track(
    request: Request,
    track_id: UUID,
    payload: schemas.WorkshopTrackUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    data = await WorkshopTrackService.update(db, track_id, payload)
    return success_response("Track berhasil diubah", data=data, request=request)

