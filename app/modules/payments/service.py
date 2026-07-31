import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments import schemas
from app.modules.payments.models import Order, PaymentStatus
from app.modules.payments.repository import PaymentRepository


class PaymentService:
    @staticmethod
    async def create_midtrans_session(session: AsyncSession, payload: schemas.CreateMidtransRequest) -> tuple[schemas.MidtransCreateResponse, Order]:
        await PaymentRepository.get_registration(session, payload.registration_id)
        order = await PaymentRepository.create_order(session, payload.registration_id)
        await PaymentRepository.create_midtrans_payment(session, order)
        return (
            schemas.MidtransCreateResponse(
                snap_token=f"snap-{order.order_number}",
                redirect_url=f"https://app.midtrans.com/snap/{order.order_number}",
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
    async def handle_midtrans_webhook(session: AsyncSession, payload: dict) -> str:
        # Placeholder untuk verifikasi signature & idempotency
        order_number = payload.get("order_id")
        if not order_number:
            from app.core.exceptions import ValidationException

            raise ValidationException(code="INVALID_WEBHOOK", message="order_id wajib ada")
        return "webhook_received"

