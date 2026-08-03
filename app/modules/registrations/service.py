import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.registrations import schemas
from app.modules.registrations.models import RegistrationStatus
from app.modules.registrations.repository import RegistrationRepository


class RegistrationService:
    @staticmethod
    def _next_registration_number() -> str:
        return f"REG-{uuid.uuid4().hex[:12].upper()}"

    @staticmethod
    async def create_registration(session: AsyncSession, payload: schemas.RegistrationCreate):
        data = payload.model_dump()
        data["registration_number"] = RegistrationService._next_registration_number()
        data["status"] = RegistrationStatus.DRAFT
        registration = await RegistrationRepository.create(session=session, **data)
        return registration

    @staticmethod
    async def get_by_id(session: AsyncSession, registration_id):
        reg = await RegistrationRepository.get_by_id(session, registration_id)
        return schemas.RegistrationRead.model_validate(reg)

    @staticmethod
    async def get_for_user(session: AsyncSession, user_id: uuid.UUID, event_id: uuid.UUID | None = None):
        registrations = await RegistrationRepository.get_for_user(session, user_id, event_id)
        return [schemas.RegistrationRead.model_validate(reg) for reg in registrations]
