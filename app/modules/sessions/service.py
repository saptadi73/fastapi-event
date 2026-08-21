from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.modules.sessions import schemas
from app.modules.sessions.repository import SessionRepository


class SessionService:
    @staticmethod
    async def list_by_event(session: AsyncSession, event_id: UUID):
        return await SessionRepository.list_by_event(session, event_id)

    @staticmethod
    async def get(session: AsyncSession, session_id: UUID):
        session_data = await SessionRepository.get(session, session_id)
        return schemas.SessionRead.model_validate(session_data)

    @staticmethod
    async def create(session: AsyncSession, payload: schemas.SessionCreate):
        data = payload.model_dump()
        if data["start_at"] >= data["end_at"]:
            raise ValidationException(code="INVALID_TIME", message="start_at harus lebih awal dari end_at")
        row = await SessionRepository.create(session, data)
        return schemas.SessionRead.model_validate(row)

    @staticmethod
    async def update(session: AsyncSession, session_id: UUID, payload: schemas.SessionUpdate):
        existing = await SessionRepository.get(session, session_id)
        updated = await SessionRepository.update(session, existing, payload.model_dump(exclude_unset=True))
        return schemas.SessionRead.model_validate(updated)

    @staticmethod
    async def delete(session: AsyncSession, session_id: UUID) -> None:
        existing = await SessionRepository.get(session, session_id)
        await SessionRepository.delete(session, existing)
