import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.payments.models import Order, OrderStatus, Payment, PaymentStatus
from app.modules.registrations.models import Registration
from app.modules.participants.models import ParticipantProfile


class PaymentRepository:
    @staticmethod
    async def get_registration(session: AsyncSession, registration_id: uuid.UUID) -> Registration:
        reg = await session.get(Registration, registration_id)
        if not reg:
            raise NotFoundException(code="REGISTRATION_NOT_FOUND", message="Registrasi tidak ditemukan")
        return reg

    @staticmethod
    async def get_latest_order(session: AsyncSession, registration_id: uuid.UUID) -> Order | None:
        stmt = (
            select(Order)
            .where(Order.registration_id == registration_id)
            .order_by(Order.created_at.desc())
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def create_order(session: AsyncSession, registration_id: uuid.UUID) -> Order:
        existing = await PaymentRepository.get_latest_order(session, registration_id)
        if existing and existing.status in [OrderStatus.PENDING, OrderStatus.DRAFT]:
            raise ConflictException(code="ORDER_EXISTS", message="Order aktif sudah ada")

        order = Order(
            registration_id=registration_id,
            order_number=f"ORD-{uuid.uuid4().hex[:16].upper()}",
            subtotal=100000,
            discount_amount=0,
            tax_amount=0,
            service_fee=0,
            total_amount=100000,
            currency="IDR",
            status=OrderStatus.PENDING,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=45),
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        return order

    @staticmethod
    async def get_order(session: AsyncSession, order_id: uuid.UUID) -> Order:
        order = await session.get(Order, order_id)
        if not order:
            raise NotFoundException(code="ORDER_NOT_FOUND", message="Order tidak ditemukan")
        return order

    @staticmethod
    async def get_payment_by_order(session: AsyncSession, order_id: uuid.UUID) -> Payment | None:
        stmt = select(Payment).where(Payment.order_id == order_id).order_by(Payment.id.desc())
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_registrations_for_user(session: AsyncSession, user_id: uuid.UUID, event_id: uuid.UUID | None = None) -> list[Registration]:
        stmt = (
            select(Registration)
            .join(ParticipantProfile, Registration.participant_id == ParticipantProfile.id)
            .where(ParticipantProfile.user_id == user_id)
            .order_by(Registration.id.desc())
        )
        if event_id:
            stmt = stmt.where(Registration.event_id == event_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_midtrans_payment(session: AsyncSession, order: Order) -> Payment:
        payment = Payment(
            order_id=order.id,
            provider="midtrans",
            gross_amount=order.total_amount,
            currency=order.currency,
            transaction_status=PaymentStatus.CREATED,
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        return payment
