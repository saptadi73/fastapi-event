from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_session
from app.core.exceptions import NotFoundException
from app.modules.users.models import User
from app.modules.participants import schemas
from app.modules.participants.service import ParticipantService
from app.support.responses import success_response

router = APIRouter(prefix="/participants")


@router.get("", summary="List participant profiles")
async def list_participants(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    profiles = await ParticipantService.list(db, page=page, size=size)
    return success_response(
        "Daftar profil peserta berhasil diambil",
        data=profiles,
        request=request,
        meta={"page": page, "size": size, "total": len(profiles), "pages": 1},
    )


@router.get("/me", summary="Get participant profile")
async def get_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    profile = await ParticipantService.get_me(db, current_user.id)
    if not profile:
        return success_response("Profile peserta belum ada", data=None, request=request)
    return success_response("Profile peserta ditemukan", data=profile, request=request)


@router.put("/me", summary="Create/replace participant profile")
async def upsert_me(
    request: Request,
    payload: schemas.ParticipantProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    profile = await ParticipantService.upsert_me(db, current_user.id, payload)
    return success_response("Profile peserta berhasil disimpan", data=profile, request=request)


@router.patch("/me", summary="Update participant profile")
async def patch_me(
    request: Request,
    payload: schemas.ParticipantProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    profile = await ParticipantService.update_me(db, current_user.id, payload)
    return success_response("Profile peserta berhasil diubah", data=profile, request=request)


@router.post("/me/photo", summary="Upload participant profile photo")
async def upload_my_photo(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    from app.core.uploads import save_profile_photo

    # Prevent orphan files when the profile has not been created yet.
    if not await ParticipantService.get_me(db, current_user.id):
        raise NotFoundException(
            code="PARTICIPANT_PROFILE_NOT_FOUND",
            message="Buat profil peserta terlebih dahulu",
        )
    photo_url = await save_profile_photo(file, "participants")
    profile = await ParticipantService.update_me(
        db,
        current_user.id,
        schemas.ParticipantProfileUpdate(profile_photo_url=photo_url),
    )
    return success_response("Foto profil peserta berhasil diunggah", data=profile, request=request)


@router.get("/{participant_id}", summary="Get participant profile")
async def get_participant(
    request: Request,
    participant_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    profile = await ParticipantService.get(db, participant_id)
    return success_response("Profil peserta ditemukan", data=profile, request=request)
