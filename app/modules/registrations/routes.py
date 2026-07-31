from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.support.responses import success_response
from app.modules.registrations import schemas
from app.modules.registrations.service import RegistrationService

router = APIRouter(prefix="/registrations")


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create registration")
async def create_registration(
    request: Request,
    payload: schemas.RegistrationCreate,
    db: AsyncSession = Depends(get_db_session),
):
    registration = await RegistrationService.create_registration(db, payload)
    return success_response(
        "Registrasi berhasil dibuat",
        data=schemas.RegistrationRead.model_validate(registration),
        request=request,
    )


@router.get("/{registration_id}", summary="Get registration")
async def get_registration(
    request: Request,
    registration_id,
    db: AsyncSession = Depends(get_db_session),
):
    registration = await RegistrationService.get_by_id(db, registration_id)
    return success_response("Registrasi ditemukan", data=registration, request=request)

