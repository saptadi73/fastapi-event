import unittest
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import ValidationException
from app.modules.payments import schemas
from app.modules.payments.models import Order, OrderKind, OrderStatus, Payment, PaymentStatus
from app.modules.payments.service import PaymentService
from app.modules.registrations.models import Registration, RegistrationStatus


class OfflineRegistrationPaymentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registration = Registration(id=uuid.uuid4(), event_id=uuid.uuid4(), participant_id=uuid.uuid4(), registration_number="REG-OFFLINE", status=RegistrationStatus.PAYMENT_PENDING)
        self.order = Order(id=uuid.uuid4(), user_id=uuid.uuid4(), registration_id=self.registration.id, event_id=self.registration.event_id, order_number="ORD-OFFLINE", order_kind=OrderKind.MAIN_REGISTRATION, subtotal=1000, total_amount=1000, currency="IDR", status=OrderStatus.PARTIALLY_PAID)
        self.admin_id = uuid.uuid4()

    @staticmethod
    def _scalar_result(value):
        result = MagicMock()
        result.scalar_one_or_none.return_value = value
        return result

    async def test_cash_payment_settles_remainder_and_returns_ticket(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.get = AsyncMock(return_value=self.registration)
        db.execute.return_value = self._scalar_result(None)
        ticket = SimpleNamespace(id=uuid.uuid4(), registration_id=self.registration.id, ticket_number="TIX-OFFLINE", status="issued")

        async def reconcile(_db, order):
            order.status = OrderStatus.PAID
            return Decimal("1000"), Decimal("0"), True

        payload = schemas.OfflineRegistrationPaymentRequest(payment_method="cash", amount=600, receipt_number="CASH-001", notes="Paid at venue")
        with patch.object(PaymentService, "_main_order_for_registration", AsyncMock(return_value=self.order)), patch.object(PaymentService, "_payment_progress", AsyncMock(return_value=(Decimal("400"), Decimal("600")))), patch.object(PaymentService, "_reconcile_order_payment", AsyncMock(side_effect=reconcile)), patch.object(PaymentService, "_notify_payment_status", AsyncMock()), patch("app.modules.tickets.repository.TicketRepository.get_by_registration", AsyncMock(return_value=None)), patch("app.modules.tickets.repository.TicketRepository.issue", AsyncMock(return_value=ticket)):
            order, payment, returned_ticket = await PaymentService.create_offline_registration_payment(db, self.registration.id, payload, self.admin_id)

        self.assertEqual(OrderStatus.PAID, order.status)
        self.assertEqual(PaymentStatus.SUCCESS, payment.transaction_status)
        self.assertEqual(Decimal("600.00"), payment.gross_amount)
        self.assertEqual("CASH-001", payment.offline_receipt_number)
        self.assertEqual(self.admin_id, payment.confirmed_by)
        self.assertIs(ticket, returned_ticket)
        db.commit.assert_awaited_once()

    async def test_offline_payment_must_equal_remaining_amount(self):
        db = AsyncMock()
        db.get = AsyncMock(return_value=self.registration)
        db.execute.return_value = self._scalar_result(None)
        payload = schemas.OfflineRegistrationPaymentRequest(payment_method="cash", amount=500, receipt_number="CASH-002")
        with patch.object(PaymentService, "_main_order_for_registration", AsyncMock(return_value=self.order)), patch.object(PaymentService, "_payment_progress", AsyncMock(return_value=(Decimal("400"), Decimal("600")))):
            with self.assertRaises(ValidationException) as caught:
                await PaymentService.create_offline_registration_payment(db, self.registration.id, payload, self.admin_id)
        self.assertEqual("OFFLINE_PAYMENT_MUST_SETTLE_REMAINDER", caught.exception.code)
        db.commit.assert_not_awaited()

    async def test_omitted_amount_uses_full_remaining_balance(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.get = AsyncMock(return_value=self.registration)
        db.execute.return_value = self._scalar_result(None)
        ticket = SimpleNamespace(id=uuid.uuid4())

        async def reconcile(_db, order):
            order.status = OrderStatus.PAID
            return Decimal("1000"), Decimal("0"), True

        payload = schemas.OfflineRegistrationPaymentRequest(payment_method="edc", receipt_number="EDC-001")
        with patch.object(PaymentService, "_main_order_for_registration", AsyncMock(return_value=self.order)), patch.object(PaymentService, "_payment_progress", AsyncMock(return_value=(Decimal("400"), Decimal("600")))), patch.object(PaymentService, "_reconcile_order_payment", AsyncMock(side_effect=reconcile)), patch.object(PaymentService, "_notify_payment_status", AsyncMock()), patch("app.modules.tickets.repository.TicketRepository.get_by_registration", AsyncMock(return_value=ticket)):
            _, payment, _ = await PaymentService.create_offline_registration_payment(db, self.registration.id, payload, self.admin_id)
        self.assertEqual(Decimal("600.00"), payment.gross_amount)


if __name__ == "__main__":
    unittest.main()
