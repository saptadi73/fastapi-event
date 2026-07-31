import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tickets import schemas
from app.modules.tickets.repository import TicketRepository


class TicketService:
    @staticmethod
    async def issue_for_registration(session: AsyncSession, registration_id: uuid.UUID) -> schemas.TicketRead:
        ticket = await TicketRepository.issue(session, registration_id)
        return schemas.TicketRead.model_validate(ticket)

    @staticmethod
    async def reissue(session: AsyncSession, ticket_id: uuid.UUID) -> schemas.TicketRead:
        ticket = await TicketRepository.reissue(session, ticket_id)
        return schemas.TicketRead.model_validate(ticket)

    @staticmethod
    async def get_qr(session: AsyncSession, ticket_id: uuid.UUID) -> dict[str, str]:
        token = await TicketRepository.get_qr_token_for_ticket(session, ticket_id)
        return {"qr_token": token, "qr_image_url": f"data:image/svg+xml;utf8,<svg>{token}</svg>"}

    @staticmethod
    async def get_user_tickets(session: AsyncSession, user_id: uuid.UUID):
        # placeholder for ownership query; untuk saat ini belum join profil-user
        return []

