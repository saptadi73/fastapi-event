import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.modules.payments.models import Order, OrderStatus, Payment, PaymentStatus, PaymentWebhookEvent
from app.modules.registrations.models import Registration
from app.modules.participants.models import ParticipantProfile


class PaymentRepository:
    @staticmethod
    async def get_registration(
        session: AsyncSession,
        registration_ref: str | uuid.UUID,
    ) -> Registration:
        """Resolve a registration by UUID or its public registration number."""
        registration_id: uuid.UUID | None = None
        if isinstance(registration_ref, uuid.UUID):
            registration_id = registration_ref
        else:
            try:
                registration_id = uuid.UUID(str(registration_ref))
            except (TypeError, ValueError):
                registration_id = None

        if registration_id is not None:
            reg = await session.get(Registration, registration_id)
        else:
            stmt = select(Registration).where(
                Registration.registration_number == str(registration_ref).strip()
            )
            result = await session.execute(stmt)
            reg = result.scalar_one_or_none()
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

        # IWBIF price is always resolved server-side from the selected package.
        from app.modules.iwbif.models import DelegatePackage, DelegateRegistrationDetail
        package_row = (await session.execute(
            select(DelegatePackage)
            .join(DelegateRegistrationDetail, DelegateRegistrationDetail.delegate_package_id == DelegatePackage.id)
            .where(DelegateRegistrationDetail.registration_id == registration_id)
        )).scalar_one_or_none()
        if not package_row:
            raise ValidationException("DELEGATE_PACKAGE_NOT_FOUND", "Paket delegate registrasi tidak ditemukan")
        # Keep the documented package display price (often USD) separate from
        # the fixed amount charged by Indonesian payment rails.
        subtotal = package_row.payment_amount_idr if package_row.payment_amount_idr is not None else package_row.amount
        currency = "IDR" if package_row.payment_amount_idr is not None else package_row.currency
        order = Order(
            registration_id=registration_id,
            order_number=f"ORD-{uuid.uuid4().hex[:16].upper()}",
            subtotal=subtotal,
            discount_amount=0,
            tax_amount=0,
            service_fee=0,
            total_amount=subtotal,
            currency=currency,
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
    async def get_payment_by_va(session: AsyncSession, virtual_account_no: str, lock: bool = False) -> Payment | None:
        stmt = select(Payment).where(Payment.virtual_account_no == virtual_account_no)
        if lock:
            stmt = stmt.with_for_update()
        return (await session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def get_payment_for_user(session: AsyncSession, payment_id: uuid.UUID, user_id: uuid.UUID) -> Payment | None:
        stmt = (select(Payment).join(Order, Payment.order_id == Order.id).join(Registration, Order.registration_id == Registration.id).join(ParticipantProfile, Registration.participant_id == ParticipantProfile.id).where(Payment.id == payment_id, ParticipantProfile.user_id == user_id))
        return (await session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def get_order_for_user(session: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID) -> Order | None:
        stmt = (select(Order).join(Registration, Order.registration_id == Registration.id).join(ParticipantProfile, Registration.participant_id == ParticipantProfile.id).where(Order.id == order_id, ParticipantProfile.user_id == user_id))
        return (await session.execute(stmt)).scalar_one_or_none()

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
    async def create_doku_payment(session: AsyncSession, order: Order) -> Payment:
        payment = Payment(
            order_id=order.id,
            provider="doku",
            gross_amount=order.total_amount,
            currency=order.currency,
            transaction_status=PaymentStatus.CREATED,
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        return payment

    @staticmethod
    async def get_order_by_number(session: AsyncSession, order_number: str, lock: bool = False) -> Order | None:
        stmt = select(Order).where(Order.order_number == order_number)
        if lock:
            stmt = stmt.with_for_update()
        return (await session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def get_webhook_event(session: AsyncSession, request_id: str, provider: str = "doku") -> PaymentWebhookEvent | None:
        stmt = select(PaymentWebhookEvent).where(PaymentWebhookEvent.provider == provider, PaymentWebhookEvent.request_id == request_id)
        return (await session.execute(stmt)).scalar_one_or_none()
