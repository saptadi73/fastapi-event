from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_session
from app.modules.check_ins import schemas
from app.modules.check_ins.service import CheckInService
from app.support.responses import success_response

router = APIRouter(prefix="/check-ins", tags=["check-ins"])


@router.post("/scan", summary="Scan QR ticket")
async def scan_check_in(
    request: Request,
    payload: schemas.CheckInScanRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    result = await CheckInService.scan(db, payload, checker_id=current_user.id)
    return success_response("Check-in berhasil", data=schemas.CheckInRead.model_validate(result), request=request)


@router.post("/manual", summary="Manual check-in")
async def manual_check_in(
    request: Request,
    payload: schemas.CheckInManualRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    result = await CheckInService.manual(db, payload, checker_id=current_user.id)
    return success_response("Manual check-in berhasil", data=schemas.CheckInRead.model_validate(result), request=request)


@router.get("", summary="List check-ins")
async def list_check_ins(
    request: Request,
    event_id: UUID | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    rows = await CheckInService.list(db, event_id=event_id)
    return success_response("Data check-in", data=rows, request=request)

