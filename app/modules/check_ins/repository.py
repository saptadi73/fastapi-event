from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.check_ins.models import CheckIn
from app.modules.tickets.models import QRToken, Ticket
from app.modules.tickets.repository import TicketRepository


class CheckInRepository:
    @staticmethod
    async def get_qr_ticket_by_token(session: AsyncSession, qr_token: str) -> Ticket:
        stmt = select(QRToken).where(QRToken.token_hash == qr_token, QRToken.is_active == True)
        result = await session.execute(stmt)
        qr = result.scalar_one_or_none()
        if not qr:
            raise NotFoundException(code="QR_NOT_FOUND", message="QR token tidak valid")
        ticket = await TicketRepository.get_by_ticket_id(session, qr.ticket_id)
        if not ticket:
            raise NotFoundException(code="TICKET_NOT_FOUND", message="Ticket tidak ditemukan")
        return ticket

    @staticmethod
    async def get_ticket_by_number(session: AsyncSession, ticket_number: str) -> Ticket:
        ticket = await TicketRepository.get_by_ticket_number(session, ticket_number)
        if not ticket:
            raise NotFoundException(code="TICKET_NOT_FOUND", message="Ticket tidak ditemukan")
        return ticket

    @staticmethod
    async def get_active_checkin(session: AsyncSession, ticket_id: UUID, event_id: UUID) -> CheckIn | None:
        stmt = select(CheckIn).where(CheckIn.ticket_id == ticket_id, CheckIn.event_id == event_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_scan(
        session: AsyncSession,
        ticket_id: UUID,
        event_id: UUID,
        check_in_type: str = "qr",
        check_in_by: UUID | None = None,
        gate_name: str | None = None,
        device_id: str | None = None,
    ) -> CheckIn:
        existing = await CheckInRepository.get_active_checkin(session, ticket_id=ticket_id, event_id=event_id)
        if existing:
            raise ConflictException(code="CHECKIN_DUPLICATE", message="Ticket sudah check-in")

        check_in = CheckIn(
            ticket_id=ticket_id,
            event_id=event_id,
            check_in_type=check_in_type,
            check_in_at=datetime.now(timezone.utc),
            check_in_by=check_in_by,
            gate_name=gate_name,
            device_id=device_id,
            status="success",
        )
        session.add(check_in)
        await session.commit()
        await session.refresh(check_in)
        return check_in

    @staticmethod
    async def list_checkins(session: AsyncSession, event_id: UUID | None = None):
        stmt = select(CheckIn).order_by(CheckIn.check_in_at.desc())
        if event_id:
            stmt = stmt.where(CheckIn.event_id == event_id)
        result = await session.execute(stmt)
        return result.scalars().all()
