from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ticket_types import schemas
from app.modules.ticket_types.repository import TicketTypeRepository


class TicketTypeService:
    @staticmethod
    async def list_by_event(session: AsyncSession, event_id: UUID):
        rows = await TicketTypeRepository.list_by_event(session, event_id)
        return [schemas.TicketTypeRead.model_validate(row) for row in rows]

    @staticmethod
    async def get(session: AsyncSession, ticket_type_id: UUID):
        row = await TicketTypeRepository.get(session, ticket_type_id)
        return schemas.TicketTypeRead.model_validate(row)

    @staticmethod
    async def create(session: AsyncSession, payload: schemas.TicketTypeCreate):
        row = await TicketTypeRepository.create(session, payload.model_dump())
        return schemas.TicketTypeRead.model_validate(row)

    @staticmethod
    async def update(session: AsyncSession, ticket_type_id: UUID, payload: schemas.TicketTypeUpdate):
        row = await TicketTypeRepository.get(session, ticket_type_id)
        row = await TicketTypeRepository.update(session, row, payload.model_dump(exclude_unset=True))
        return schemas.TicketTypeRead.model_validate(row)

