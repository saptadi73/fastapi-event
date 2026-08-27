import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.dialects import postgresql

from app.modules.payments.models import Order, Payment
from app.modules.payments.reporting import PaymentReportingService
from app.modules.payments.schemas import TransactionStatusUpdateRequest
from app.modules.payments.service import PaymentService
from app.modules.registrations.models import Registration, RegistrationStatus


def scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


class TransactionManagementTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_provider_query_does_not_add_provider_filter(self):
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        session.execute.return_value = result

        await PaymentReportingService.rows(session, provider=None)

        statement = session.execute.await_args.args[0]
        sql = str(statement.compile(dialect=postgresql.dialect())).lower()
        self.assertNotIn("payments.provider like", sql)
        self.assertNotIn("payments.provider =", sql)

    async def test_paid_action_synchronizes_payment_order_and_registration(self):
        payment_id = uuid.uuid4()
        registration_id = uuid.uuid4()
        order = Order(
            id=uuid.uuid4(), user_id=uuid.uuid4(), registration_id=registration_id,
            order_number="ORD-1", subtotal=100, total_amount=100,
            currency="IDR", status="pending",
        )
        payment = Payment(
            id=payment_id, order_id=order.id, provider="midtrans",
            gross_amount=100, currency="IDR", transaction_status="pending",
        )
        registration = Registration(
            id=registration_id, event_id=uuid.uuid4(), participant_id=uuid.uuid4(),
            registration_number="REG-1", status=RegistrationStatus.PAYMENT_PENDING,
        )
        session = AsyncMock()
        session.add = MagicMock()

        async def get(model, identifier, **kwargs):
            return {Payment: payment, Order: order, Registration: registration}.get(model)

        session.get.side_effect = get
        with patch.object(PaymentService, "_notify_payment_status", AsyncMock()):
            returned_order, returned_payment = await PaymentService.update_transaction_status(
                session, payment_id, TransactionStatusUpdateRequest(status="paid"), uuid.uuid4()
            )

        self.assertIs(order, returned_order)
        self.assertIs(payment, returned_payment)
        self.assertEqual("success", payment.transaction_status)
        self.assertEqual("paid", order.status)
        self.assertEqual(RegistrationStatus.PAID, registration.status)
        self.assertIsNotNone(payment.paid_at)
        session.commit.assert_awaited_once()

    async def test_cancelled_action_keeps_order_paid_when_another_payment_succeeded(self):
        payment_id = uuid.uuid4()
        order = Order(
            id=uuid.uuid4(), user_id=uuid.uuid4(), registration_id=None,
            order_number="ORD-2", subtotal=100, total_amount=100,
            currency="IDR", status="paid",
        )
        payment = Payment(
            id=payment_id, order_id=order.id, provider="doku",
            gross_amount=100, currency="IDR", transaction_status="success",
        )
        session = AsyncMock()
        session.add = MagicMock()
        session.get.side_effect = lambda model, identifier, **kwargs: payment if model is Payment else order
        session.execute.return_value = scalar_result(uuid.uuid4())

        with patch.object(PaymentService, "_notify_payment_status", AsyncMock()):
            await PaymentService.update_transaction_status(
                session, payment_id, TransactionStatusUpdateRequest(status="cancelled"), uuid.uuid4()
            )

        self.assertEqual("cancelled", payment.transaction_status)
        self.assertEqual("paid", order.status)
        self.assertIsNone(payment.paid_at)

    async def test_delete_reverts_paid_order_when_no_successful_payment_remains(self):
        payment_id = uuid.uuid4()
        order = Order(
            id=uuid.uuid4(), user_id=uuid.uuid4(), registration_id=None,
            order_number="ORD-3", subtotal=100, total_amount=100,
            currency="IDR", status="paid",
        )
        payment = Payment(
            id=payment_id, order_id=order.id, provider="manual_transfer",
            gross_amount=100, currency="IDR", transaction_status="success",
        )
        proofs_result = MagicMock()
        proofs_result.scalars.return_value.all.return_value = []
        session = AsyncMock()
        session.get.side_effect = lambda model, identifier, **kwargs: payment if model is Payment else order
        session.execute.side_effect = [proofs_result, MagicMock(), MagicMock(), scalar_result(None)]

        returned_order_id, proof_paths = await PaymentService.delete_transaction(session, payment_id)

        self.assertEqual(order.id, returned_order_id)
        self.assertEqual([], proof_paths)
        self.assertEqual("pending", order.status)
        session.delete.assert_awaited_once_with(payment)
        session.commit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
