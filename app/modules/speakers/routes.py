from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_session, require_admin
from app.support.responses import success_response
from app.modules.speakers import schemas
from app.modules.speakers.service import SpeakerService

router = APIRouter(prefix="/speakers", tags=["speakers"])


@router.get("", summary="List speakers")
async def list_speakers(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
):
    rows = await SpeakerService.list(db, page=page, size=size)
    data = [schemas.SpeakerRead.model_validate(row) for row in rows]
    return success_response("List speaker berhasil", data=data, request=request, meta={"page": page, "size": size, "total": len(data), "pages": 1})


@router.get("/{speaker_id}", summary="Get speaker")
async def get_speaker(
    request: Request,
    speaker_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    speaker = await SpeakerService.get(db, speaker_id)
    return success_response("Speaker ditemukan", data=speaker, request=request)


@router.post("", summary="Create speaker")
async def create_speaker(
    request: Request,
    payload: schemas.SpeakerCreate,
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(require_admin),
):
    speaker = await SpeakerService.create(db, payload)
    return success_response("Speaker berhasil dibuat", data=speaker, request=request)


@router.put("/{speaker_id}", summary="Update speaker")
async def update_speaker(
    request: Request,
    speaker_id: UUID,
    payload: schemas.SpeakerUpdate,
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(require_admin),
):
    speaker = await SpeakerService.update(db, speaker_id, payload)
    return success_response("Speaker berhasil diubah", data=speaker, request=request)


@router.post("/{speaker_id}/photo", summary="Upload speaker photo")
async def upload_speaker_photo(
    request: Request,
    speaker_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(require_admin),
):
    from app.core.uploads import delete_uploaded_file, save_profile_photo

    # Validate the UUID-backed record before writing a file to disk.
    current = await SpeakerService.get(db, speaker_id)
    photo_url = await save_profile_photo(file, "speakers")
    try:
        speaker = await SpeakerService.update(
            db,
            speaker_id,
            schemas.SpeakerUpdate(profile_photo_url=photo_url),
        )
    except Exception:
        delete_uploaded_file(photo_url)
        raise
    if current.profile_photo_url and current.profile_photo_url != photo_url:
        delete_uploaded_file(current.profile_photo_url)
    return success_response("Foto speaker berhasil diunggah", data=speaker, request=request)


@router.delete("/{speaker_id}", summary="Delete speaker")
async def delete_speaker(request: Request, speaker_id: UUID, db: AsyncSession = Depends(get_db_session), admin=Depends(require_admin)):
    await SpeakerService.delete(db, speaker_id)
    return success_response("Speaker berhasil dihapus", data={"id": speaker_id}, request=request)


@router.post("/{speaker_id}/events", summary="Assign speaker to event")
async def assign_speaker_event(request: Request, speaker_id: UUID, payload: schemas.EventSpeakerWrite, db: AsyncSession = Depends(get_db_session), admin=Depends(require_admin)):
    await SpeakerService.assign_event(db, speaker_id, payload.event_id)
    return success_response("Speaker berhasil dihubungkan ke event", data={"speaker_id": speaker_id, "event_id": payload.event_id}, request=request)


@router.delete("/{speaker_id}/events/{event_id}", summary="Remove speaker from event")
async def remove_speaker_event(request: Request, speaker_id: UUID, event_id: UUID, db: AsyncSession = Depends(get_db_session), admin=Depends(require_admin)):
    await SpeakerService.remove_event(db, speaker_id, event_id)
    return success_response("Relasi speaker dan event berhasil dihapus", data={"speaker_id": speaker_id, "event_id": event_id}, request=request)
