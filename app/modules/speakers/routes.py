from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
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
    speaker_id,
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
    speaker_id,
    payload: schemas.SpeakerUpdate,
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(require_admin),
):
    speaker = await SpeakerService.update(db, speaker_id, payload)
    return success_response("Speaker berhasil diubah", data=speaker, request=request)


@router.post("/{speaker_id}/photo", summary="Upload speaker photo")
async def upload_speaker_photo(
    request: Request,
    speaker_id,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(require_admin),
):
    from app.core.uploads import save_profile_photo

    photo_url = await save_profile_photo(file, "speakers")
    speaker = await SpeakerService.update(
        db,
        speaker_id,
        schemas.SpeakerUpdate(profile_photo_url=photo_url),
    )
    return success_response("Foto speaker berhasil diunggah", data=speaker, request=request)
