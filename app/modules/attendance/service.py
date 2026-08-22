from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.check_ins import schemas as check_in_schemas
from app.modules.check_ins import repository as check_in_repo
from app.modules.attendance import schemas
from app.modules.attendance import repository as attendance_repo


class AttendanceService:
    @staticmethod
    async def scan_by_qr(
        session: AsyncSession,
        payload: check_in_schemas.CheckInScanRequest,
        checker_id: UUID | None = None,
    ):
        ticket = await check_in_repo.CheckInRepository.get_qr_ticket_by_token(
            session=session,
            qr_token=payload.qr_token,
            event_id=payload.event_id,
        )

        check_in = await check_in_repo.CheckInRepository.create_scan(
            session=session,
            ticket_id=ticket.id,
            event_id=payload.event_id,
            check_in_type="qr",
            check_in_by=checker_id,
            gate_name=payload.gate_name,
            device_id=payload.device_id,
        )

        registrant = await attendance_repo.AttendanceRepository.get_attendee_by_ticket(
            session=session,
            event_id=payload.event_id,
            ticket_id=ticket.id,
        )
        return {
            "check_in": check_in,
            "registrant": registrant,
        }

    @staticmethod
    async def get_event_report(
        session: AsyncSession,
        event_id: UUID,
        include_without_ticket: bool = True,
    ) -> schemas.AttendanceReport:
        attendees = await attendance_repo.AttendanceRepository.list_event_attendees(
            session=session,
            event_id=event_id,
            include_without_ticket=include_without_ticket,
        )
        total_registered = len(attendees)
        total_checked_in = sum(1 for row in attendees if row["is_checked_in"])
        total_not_checked_in = total_registered - total_checked_in
        attendance_rate = 0.0 if total_registered == 0 else round((total_checked_in / total_registered) * 100, 2)

        summary = schemas.AttendanceSummary(
            event_id=event_id,
            total_registered=total_registered,
            total_checked_in=total_checked_in,
            total_not_checked_in=total_not_checked_in,
            attendance_rate=attendance_rate,
        )
        return schemas.AttendanceReport(event_id=event_id, summary=summary, attendees=attendees)

    @staticmethod
    async def get_roster_row(
        session: AsyncSession,
        event_id: UUID,
        registration_id: UUID,
    ) -> schemas.AttendanceRegistrant:
        row = await attendance_repo.AttendanceRepository.get_attendee_by_registration(
            session=session,
            event_id=event_id,
            registration_id=registration_id,
        )
        return schemas.AttendanceRegistrant.model_validate(row)
