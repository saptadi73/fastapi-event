from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.modules.check_ins.models import CheckIn
from app.modules.participants.models import ParticipantProfile
from app.modules.registrations.models import Registration, RegistrationStatus
from app.modules.tickets.models import Ticket


class AttendanceRepository:
    @staticmethod
    async def get_attendee_by_ticket(session: AsyncSession, event_id: UUID, ticket_id: UUID) -> dict:
        stmt = AttendanceRepository._build_attendee_query(event_id)
        result = await session.execute(stmt.where(Ticket.id == ticket_id))
        row = result.mappings().first()
        if not row:
            raise NotFoundException(code="ATTENDANCE_NOT_FOUND", message="Data registran tidak ditemukan untuk ticket ini")
        return AttendanceRepository._to_response_dict(row)

    @staticmethod
    async def get_attendee_by_registration(session: AsyncSession, event_id: UUID, registration_id: UUID) -> dict:
        stmt = AttendanceRepository._build_attendee_query(event_id)
        result = await session.execute(stmt.where(Registration.id == registration_id))
        row = result.mappings().first()
        if not row:
            raise NotFoundException(code="ATTENDANCE_NOT_FOUND", message="Data registran tidak ditemukan")
        return AttendanceRepository._to_response_dict(row)

    @staticmethod
    async def list_event_attendees(
        session: AsyncSession,
        event_id: UUID,
        include_without_ticket: bool = True,
    ):
        stmt = AttendanceRepository._build_attendee_query(event_id)
        if not include_without_ticket:
            stmt = stmt.where(Ticket.id.is_not(None))
        result = await session.execute(stmt)
        return [AttendanceRepository._to_response_dict(row) for row in result.mappings().all()]

    @staticmethod
    def _build_attendee_query(event_id: UUID):
        return (
            select(
                Registration.id.label("registration_id"),
                Registration.event_id.label("event_id"),
                Registration.registration_number.label("registration_number"),
                Registration.status.label("registration_status"),
                ParticipantProfile.id.label("participant_id"),
                ParticipantProfile.full_name.label("participant_name"),
                ParticipantProfile.organization_name.label("organization_name"),
                Ticket.id.label("ticket_id"),
                Ticket.ticket_number.label("ticket_number"),
                CheckIn.id.label("check_in_id"),
                CheckIn.check_in_type.label("check_in_type"),
                CheckIn.check_in_at.label("check_in_at"),
                CheckIn.gate_name.label("gate_name"),
                CheckIn.device_id.label("device_id"),
                CheckIn.check_in_by.label("check_in_by"),
            )
            .select_from(Registration)
            .join(ParticipantProfile, ParticipantProfile.id == Registration.participant_id)
            .outerjoin(Ticket, Ticket.registration_id == Registration.id)
            .outerjoin(
                CheckIn,
                and_(
                    CheckIn.ticket_id == Ticket.id,
                    CheckIn.event_id == event_id,
                ),
            )
            .where(
                Registration.event_id == event_id,
                Registration.status != RegistrationStatus.CANCELED,
                Registration.status != RegistrationStatus.CANCELLED,
            )
            .order_by(Registration.registration_number.asc(), ParticipantProfile.full_name.asc())
        )

    @staticmethod
    def _to_response_dict(row) -> dict:
        is_checked_in = row["check_in_id"] is not None
        return {
            "registration_id": row["registration_id"],
            "event_id": row["event_id"],
            "registration_number": row["registration_number"],
            "registration_status": row["registration_status"],
            "participant_id": row["participant_id"],
            "participant_name": row["participant_name"],
            "organization_name": row["organization_name"],
            "ticket_id": row["ticket_id"],
            "ticket_number": row["ticket_number"],
            "is_checked_in": is_checked_in,
            "check_in_id": row["check_in_id"],
            "check_in_type": row["check_in_type"],
            "check_in_at": row["check_in_at"],
            "gate_name": row["gate_name"],
            "device_id": row["device_id"],
            "check_in_by": row["check_in_by"],
        }
