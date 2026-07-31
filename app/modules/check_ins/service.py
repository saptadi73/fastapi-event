from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.check_ins import schemas
from app.modules.check_ins.repository import CheckInRepository


class CheckInService:
    @staticmethod
    async def scan(session: AsyncSession, payload: schemas.CheckInScanRequest, checker_id: UUID | None = None):
        ticket = await CheckInRepository.get_qr_ticket_by_token(session, payload.qr_token)
        ci = await CheckInRepository.create_scan(
            session=session,
            ticket_id=ticket.id,
            event_id=payload.event_id,
            check_in_type="qr",
            check_in_by=checker_id,
            gate_name=payload.gate_name,
            device_id=payload.device_id,
        )
        return ci

    @staticmethod
    async def manual(session: AsyncSession, payload: schemas.CheckInManualRequest, checker_id: UUID | None = None):
        ticket = await CheckInRepository.get_ticket_by_number(session, payload.ticket_number)
        ci = await CheckInRepository.create_scan(
            session=session,
            ticket_id=ticket.id,
            event_id=payload.event_id,
            check_in_type="manual",
            check_in_by=checker_id,
            gate_name=payload.gate_name,
            device_id=payload.device_id,
        )
        return ci

    @staticmethod
    async def list(session: AsyncSession, event_id: UUID | None = None):
        rows = await CheckInRepository.list_checkins(session, event_id=event_id)
        return [schemas.CheckInRead.model_validate(row) for row in rows]

