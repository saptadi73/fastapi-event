from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_admin
from app.core.exceptions import ValidationException
from app.modules.participants.reporting import ParticipantReportingService
from app.modules.payments.reporting import PAYMENT_STATUSES
from app.modules.users.models import User
from app.support.responses import success_response


router = APIRouter(prefix="/admin/reports/participants", tags=["admin-participant-reports"])


async def _rows(db, event_id, package_id, payment_status, search):
    normalized_status = payment_status.strip().lower() if payment_status else None
    if normalized_status and normalized_status not in PAYMENT_STATUSES:
        raise ValidationException("INVALID_PAYMENT_STATUS", "Status pembayaran tidak valid")
    return await ParticipantReportingService.rows(
        db,
        event_id=event_id,
        package_id=package_id,
        payment_status=normalized_status,
        search=search,
    )


@router.get("")
async def participant_report(
    request: Request,
    event_id: UUID | None = Query(default=None),
    package_id: UUID | None = Query(default=None),
    payment_status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    rows = await _rows(db, event_id, package_id, payment_status, search)
    total = len(rows)
    offset = (page - 1) * size
    return success_response(
        "Laporan participant berhasil diambil",
        data=rows[offset:offset + size],
        meta={"page": page, "size": size, "total": total, "pages": max((total + size - 1) // size, 1)},
        request=request,
    )


@router.get(".csv")
async def participant_report_csv(
    event_id: UUID | None = Query(default=None),
    package_id: UUID | None = Query(default=None),
    payment_status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    rows = await _rows(db, event_id, package_id, payment_status, search)
    filename = f"participant-packages-{datetime.now().date().isoformat()}.csv"
    return Response(
        ParticipantReportingService.csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
