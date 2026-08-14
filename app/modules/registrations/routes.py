import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_session
from app.modules.users.models import User
from app.support.responses import success_response
from app.modules.registrations import schemas
from app.modules.registrations.service import RegistrationService

router = APIRouter(prefix="/registrations")


@router.get("/me", summary="Get registrations for current user")
async def get_my_registrations(
    request: Request,
    event_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    registrations = await RegistrationService.get_for_user(db, current_user.id, event_id)
    return success_response(
        "Daftar registrasi pengguna ditemukan",
        data=registrations,
        request=request,
    )


@router.get("/{registration_id}", summary="Get registration")
async def get_registration(
    request: Request,
    registration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    registration = await RegistrationService.get_by_id(db, registration_id, current_user.id)
    return success_response("Registrasi ditemukan", data=registration, request=request)
