import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationException
from app.modules.ticket_types.models import TicketType


class TicketTypeRepository:
    @staticmethod
    async def list_by_event(session: AsyncSession, event_id: uuid.UUID):
        stmt = select(TicketType).where(TicketType.event_id == event_id).order_by(TicketType.created_at.desc())
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get(session: AsyncSession, ticket_type_id: uuid.UUID) -> TicketType:
        data = await session.get(TicketType, ticket_type_id)
        if not data:
            raise NotFoundException(code="TICKET_TYPE_NOT_FOUND", message="Ticket type tidak ditemukan")
        return data

    @staticmethod
    async def create(session: AsyncSession, payload: dict) -> TicketType:
        if payload.get("sales_start_at") and payload.get("sales_end_at") and payload["sales_start_at"] >= payload["sales_end_at"]:
            raise ValidationException(code="INVALID_TIME", message="sales_start_at harus sebelum sales_end_at")
        obj = TicketType(**payload)
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj

    @staticmethod
    async def update(session: AsyncSession, obj: TicketType, data: dict) -> TicketType:
        for key, value in data.items():
            if value is not None:
                setattr(obj, key, value)
        await session.commit()
        await session.refresh(obj)
        return obj

