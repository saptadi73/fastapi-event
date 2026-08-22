from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_admin
from app.modules.attendance import schemas, service
from app.modules.check_ins import schemas as check_in_schemas
from app.modules.users.models import User
from app.support.responses import success_response


router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.post("/scan", summary="Scan QR untuk check-in (Hari-H)", status_code=status.HTTP_201_CREATED)
async def scan_attendance(
    request: Request,
    payload: check_in_schemas.CheckInScanRequest,
    db: AsyncSession = Depends(get_db_session),
    admin: User = Depends(require_admin),
):
    result = await service.AttendanceService.scan_by_qr(db, payload, checker_id=admin.id)
    check_in = result["check_in"]
    registrant = schemas.AttendanceRegistrant.model_validate(result["registrant"])

    response = {
        "check_in": {
            "id": str(check_in.id),
            "ticket_id": str(check_in.ticket_id),
            "event_id": str(check_in.event_id),
            "check_in_type": check_in.check_in_type,
            "check_in_at": check_in.check_in_at.isoformat(),
            "check_in_by": str(check_in.check_in_by) if check_in.check_in_by else None,
            "gate_name": check_in.gate_name,
            "device_id": check_in.device_id,
            "status": check_in.status,
            "notes": check_in.notes,
        },
        "registrant": registrant,
    }
    return success_response("Absensi berhasil", data=response, request=request)


@router.get("/events/{event_id}/report", summary="Laporan kehadiran event (terdaftar + hadir)")
async def attendance_report(
    request: Request,
    event_id: UUID,
    include_without_ticket: bool = Query(default=True),
    db: AsyncSession = Depends(get_db_session),
    admin: User = Depends(require_admin),
):
    report = await service.AttendanceService.get_event_report(
        session=db,
        event_id=event_id,
        include_without_ticket=include_without_ticket,
    )
    return success_response("Laporan kehadiran event ditemukan", data=report.model_dump(), request=request)


@router.get("/events/{event_id}/roster/{registration_id}", summary="Detail registran attendance")
async def attendance_roster_row(
    request: Request,
    event_id: UUID,
    registration_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    admin: User = Depends(require_admin),
):
    row = await service.AttendanceService.get_roster_row(
        session=db,
        event_id=event_id,
        registration_id=registration_id,
    )
    return success_response("Data registran attendance ditemukan", data=row, request=request)
