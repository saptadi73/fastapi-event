import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ConflictException
from app.modules.participants.models import ParticipantProfile
from app.modules.payments.models import Order, OrderStatus
from app.modules.store.models import OrderItem
from app.modules.registrations.models import Registration
from app.modules.registrations.repository import RegistrationRepository
from app.modules.tickets.models import QRToken, Ticket
from sqlalchemy import select


class TicketRepository:
    @staticmethod
    async def get_by_registration(session: AsyncSession, registration_id: uuid.UUID) -> Ticket | None:
        stmt = select(Ticket).where(Ticket.registration_id == registration_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_ticket_id(session: AsyncSession, ticket_id: uuid.UUID) -> Ticket | None:
        return await session.get(Ticket, ticket_id)

    @staticmethod
    async def get_by_ticket_number(session: AsyncSession, ticket_number: str) -> Ticket | None:
        stmt = select(Ticket).where(Ticket.ticket_number == ticket_number)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_user_id(session: AsyncSession, user_id: uuid.UUID) -> list[Ticket]:
        stmt = (
            select(Ticket)
            .join(Registration, Registration.id == Ticket.registration_id)
            .join(ParticipantProfile, ParticipantProfile.id == Registration.participant_id)
            .join(Order, Order.registration_id == Registration.id)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(
                ParticipantProfile.user_id == user_id,
                Order.status == OrderStatus.PAID,
                OrderItem.product_type == "delegate",
                Ticket.status == "issued",
            )
            .order_by(Ticket.created_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_owned_by_ticket_id(session: AsyncSession, ticket_id: uuid.UUID, user_id: uuid.UUID) -> Ticket:
        stmt = (
            select(Ticket)
            .join(Registration, Registration.id == Ticket.registration_id)
            .join(ParticipantProfile, ParticipantProfile.id == Registration.participant_id)
            .join(Order, Order.registration_id == Registration.id)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(
                Ticket.id == ticket_id,
                ParticipantProfile.user_id == user_id,
                Order.status == OrderStatus.PAID,
                OrderItem.product_type == "delegate",
                Ticket.status == "issued",
            )
        )
        result = await session.execute(stmt)
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise NotFoundException(code="TICKET_NOT_FOUND", message="Ticket tidak ditemukan")
        return ticket

    @staticmethod
    async def issue(session: AsyncSession, registration_id: uuid.UUID) -> Ticket:
        await RegistrationRepository.get_by_id(session, registration_id)
        paid_order = (await session.execute(
            select(Order.id).join(OrderItem, OrderItem.order_id == Order.id).where(
                Order.registration_id == registration_id,
                Order.status == OrderStatus.PAID,
                OrderItem.product_type == "delegate",
            ).limit(1)
        )).scalar_one_or_none()
        if paid_order is None:
            raise ConflictException(
                code="REGISTRATION_PAYMENT_REQUIRED",
                message="Seluruh bagian pembayaran harus lunas sebelum ticket diterbitkan",
            )
        existing = await TicketRepository.get_by_registration(session, registration_id)
        if existing:
            raise ConflictException(code="TICKET_EXISTS", message="Ticket sudah ada untuk registrasi ini")

        ticket = Ticket(
            registration_id=registration_id,
            ticket_number=f"TIX-{uuid.uuid4().hex[:12].upper()}",
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)

        qr = QRToken(
            ticket_id=ticket.id,
            token_hash=f"qr-{uuid.uuid4().hex}",
            is_active=True,
        )
        session.add(qr)
        await session.commit()
        return ticket

    @staticmethod
    async def reissue(session: AsyncSession, ticket_id: uuid.UUID) -> Ticket:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            raise NotFoundException(code="TICKET_NOT_FOUND", message="Ticket tidak ditemukan")
        ticket.status = "revoked"
        await session.commit()
        await session.refresh(ticket)
        return await TicketRepository.issue(session, ticket.registration_id)

    @staticmethod
    async def get_qr_token_for_ticket(session: AsyncSession, ticket_id: uuid.UUID) -> str:
        stmt = select(QRToken).where(QRToken.ticket_id == ticket_id, QRToken.is_active == True)
        result = await session.execute(stmt)
        qr = result.scalars().first()
        if not qr:
            raise NotFoundException(code="QR_NOT_FOUND", message="QR token tidak ditemukan")
        return qr.token_hash
