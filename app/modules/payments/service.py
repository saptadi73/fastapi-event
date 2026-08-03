import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments import schemas
from app.modules.payments.models import Order, OrderStatus
from app.modules.payments.repository import PaymentRepository
from app.modules.events.models import Event
from app.modules.participants.models import ParticipantProfile
from app.modules.ticket_types.models import TicketType
from app.modules.users.models import User


class PaymentService:
    @staticmethod
    async def create_midtrans_session(session: AsyncSession, payload: schemas.CreateMidtransRequest) -> tuple[schemas.MidtransCreateResponse, Order]:
        await PaymentRepository.get_registration(session, payload.registration_id)
        latest_order = await PaymentRepository.get_latest_order(session, payload.registration_id)
        if latest_order and latest_order.status == OrderStatus.PAID:
            latest_payment = await PaymentRepository.get_payment_by_order(session, latest_order.id)
            payment_id = latest_payment.id if latest_payment else None
            return (
                schemas.MidtransCreateResponse(
                    snap_token="",
                    redirect_url="",
                    already_paid=True,
                    payment_id=payment_id,
                    order_status=latest_order.status,
                    requires_payment=False,
                ),
                latest_order,
            )

        if latest_order and latest_order.status in [OrderStatus.PENDING, OrderStatus.DRAFT]:
            payment = await PaymentRepository.get_payment_by_order(session, latest_order.id)
            if not payment:
                payment = await PaymentRepository.create_midtrans_payment(session, latest_order)
            return (
                schemas.MidtransCreateResponse(
                    snap_token=f"snap-{latest_order.order_number}",
                    redirect_url=f"https://app.midtrans.com/snap/{latest_order.order_number}",
                    already_paid=False,
                    payment_id=payment.id if payment else None,
                    order_status=latest_order.status,
                    requires_payment=True,
                ),
                latest_order,
            )

        order = await PaymentRepository.create_order(session, payload.registration_id)
        payment = await PaymentRepository.create_midtrans_payment(session, order)

        return (
            schemas.MidtransCreateResponse(
                snap_token=f"snap-{order.order_number}",
                redirect_url=f"https://app.midtrans.com/snap/{order.order_number}",
                already_paid=False,
                payment_id=payment.id,
                order_status=order.status,
                requires_payment=True,
            ),
            order,
        )

    @staticmethod
    async def get_payment(session: AsyncSession, payment_id: uuid.UUID):
        from app.modules.payments.models import Payment

        payment = await session.get(Payment, payment_id)
        if not payment:
            from app.core.exceptions import NotFoundException

            raise NotFoundException(code="PAYMENT_NOT_FOUND", message="Payment tidak ditemukan")
        return payment

    @staticmethod
    async def get_order(session: AsyncSession, order_id: uuid.UUID):
        return await PaymentRepository.get_order(session, order_id)

    @staticmethod
    async def get_invoice(session: AsyncSession, registration_ref: str | uuid.UUID) -> schemas.InvoiceRead:
        reg = await PaymentRepository.get_registration(session, registration_ref)
        participant = await session.get(ParticipantProfile, reg.participant_id)
        if not participant:
            from app.core.exceptions import NotFoundException

            raise NotFoundException(code="PARTICIPANT_NOT_FOUND", message="Profil peserta tidak ditemukan")

        user = await session.get(User, participant.user_id)
        event = await session.get(Event, reg.event_id)
        ticket_type = await session.get(TicketType, reg.ticket_type_id) if reg.ticket_type_id else None
        order = await PaymentRepository.get_latest_order(session, reg.id)
        payment = None
        if order:
            payment = await PaymentRepository.get_payment_by_order(session, order.id)

        order_data = None
        if order:
            order_data = schemas.OrderRead.model_validate(order)
        payment_data = None
        if payment:
            payment_data = schemas.PaymentRead.model_validate(payment)

        return schemas.InvoiceRead(
            registration=schemas.InvoiceRegistration(
                id=reg.id,
                registration_number=reg.registration_number,
                status=reg.status,
                event_id=reg.event_id,
                event_name=event.name if event else None,
                participant_id=reg.participant_id,
                ticket_type_id=reg.ticket_type_id,
                ticket_type_code=ticket_type.code if ticket_type else None,
                ticket_type_name=ticket_type.name if ticket_type else None,
                confirmed_at=reg.confirmed_at,
            ),
            participant=schemas.InvoiceParticipant(
                id=participant.id,
                full_name=participant.full_name,
                organization_name=participant.organization_name,
                email=user.email if user else "",
            ),
            order=order_data,
            payment=payment_data,
        )

    @staticmethod
    async def get_my_invoices(session: AsyncSession, user_id: uuid.UUID, event_id: uuid.UUID | None = None) -> list[schemas.InvoiceRead]:
        registrations = await PaymentRepository.get_registrations_for_user(session, user_id, event_id)
        if not registrations:
            return []

        result: list[schemas.InvoiceRead] = []
        for reg in registrations:
            participant = await session.get(ParticipantProfile, reg.participant_id)
            if not participant:
                continue
            user = await session.get(User, participant.user_id)
            event = await session.get(Event, reg.event_id)
            ticket_type = await session.get(TicketType, reg.ticket_type_id) if reg.ticket_type_id else None
            order = await PaymentRepository.get_latest_order(session, reg.id)
            payment = await PaymentRepository.get_payment_by_order(session, order.id) if order else None

            registration = schemas.InvoiceRegistration(
                id=reg.id,
                registration_number=reg.registration_number,
                status=reg.status,
                event_id=reg.event_id,
                event_name=event.name if event else None,
                participant_id=reg.participant_id,
                ticket_type_id=reg.ticket_type_id,
                ticket_type_code=ticket_type.code if ticket_type else None,
                ticket_type_name=ticket_type.name if ticket_type else None,
                confirmed_at=reg.confirmed_at,
            )
            participant_info = schemas.InvoiceParticipant(
                id=participant.id,
                full_name=participant.full_name,
                organization_name=participant.organization_name,
                email=user.email if user else "",
            )
            result.append(
                schemas.InvoiceRead(
                    registration=registration,
                    participant=participant_info,
                    order=schemas.OrderRead.model_validate(order) if order else None,
                    payment=schemas.PaymentRead.model_validate(payment) if payment else None,
                )
            )
        return result

    @staticmethod
    async def handle_midtrans_webhook(session: AsyncSession, payload: dict) -> str:
        # Placeholder untuk verifikasi signature & idempotency
        order_number = payload.get("order_id")
        if not order_number:
            from app.core.exceptions import ValidationException

            raise ValidationException(code="INVALID_WEBHOOK", message="order_id wajib ada")
        return "webhook_received"
