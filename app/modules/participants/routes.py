from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_session
from app.modules.users.models import User
from app.modules.participants import schemas
from app.modules.participants.service import ParticipantService
from app.support.responses import success_response

router = APIRouter(prefix="/participants")


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

