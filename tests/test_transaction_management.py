import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.dialects import postgresql

from app.modules.payments.models import Order, Payment, payment_allowed_actions
from app.modules.payments.reporting import PaymentReportingService
from app.modules.payments.schemas import TransactionBulkActionRequest, TransactionStatusUpdateRequest
from app.modules.payments.service import PaymentService
from app.modules.registrations.models import Registration, RegistrationStatus
from app.core.exceptions import ConflictException


def scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


class TransactionManagementTests(unittest.IsolatedAsyncioTestCase):
    def test_allowed_actions_are_derived_from_backend_transition_rules(self):
        editable = ["paid", "success", "canceled", "delete"]
        for status in ("created", "pending", "failed", "expired", "canceled"):
            self.assertEqual(editable, payment_allowed_actions(status))
        self.assertEqual(["paid", "success"], payment_allowed_actions("success"))
        self.assertEqual([], payment_allowed_actions("refunded"))

    def test_soft_deleted_transaction_has_no_allowed_actions(self):
        from datetime import datetime, timezone

        self.assertEqual([], payment_allowed_actions("pending", datetime.now(timezone.utc)))

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
        self.assertIn("payments.deleted_at is null", sql)

    async def test_admin_query_can_explicitly_include_soft_deleted(self):
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        session.execute.return_value = result

        await PaymentReportingService.rows(session, provider=None, include_deleted=True)

        statement = session.execute.await_args.args[0]
        sql = str(statement.compile(dialect=postgresql.dialect())).lower()
        self.assertNotIn("payments.deleted_at is null", sql)

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
        with patch.object(PaymentService, "_notify_payment_status", AsyncMock()), patch.object(PaymentService, "_payment_progress", AsyncMock(return_value=(100, 0))):
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

    async def test_success_transaction_cannot_be_canceled(self):
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
        with patch.object(PaymentService, "_notify_payment_status", AsyncMock()):
            with self.assertRaises(ConflictException) as caught:
                await PaymentService.update_transaction_status(
                    session, payment_id, TransactionStatusUpdateRequest(status="canceled"), uuid.uuid4()
                )

        self.assertEqual("INVALID_PAYMENT_STATUS_TRANSITION", caught.exception.code)
        self.assertEqual("success", payment.transaction_status)
        self.assertEqual("paid", order.status)

    async def test_delete_is_soft_and_reverts_order_when_no_successful_payment_remains(self):
        payment_id = uuid.uuid4()
        order = Order(
            id=uuid.uuid4(), user_id=uuid.uuid4(), registration_id=None,
            order_number="ORD-3", subtotal=100, total_amount=100,
            currency="IDR", status="pending",
        )
        payment = Payment(
            id=payment_id, order_id=order.id, provider="manual_transfer",
            gross_amount=100, currency="IDR", transaction_status="pending",
        )
        session = AsyncMock()
        session.add = MagicMock()
        session.get.side_effect = lambda model, identifier, **kwargs: payment if model is Payment else order
        session.execute.return_value = scalar_result(None)
        actor_id = uuid.uuid4()

        returned_order, returned_payment = await PaymentService.delete_transaction(
            session, payment_id, actor_id, "duplicate"
        )

        self.assertIs(order, returned_order)
        self.assertIs(payment, returned_payment)
        self.assertEqual("pending", order.status)
        self.assertIsNotNone(payment.deleted_at)
        self.assertEqual(actor_id, payment.deleted_by)
        self.assertEqual("duplicate", payment.deletion_reason)
        self.assertEqual("SOFT_DELETED", session.add.call_args.args[0].event_status)
        session.delete.assert_not_awaited()
        session.commit.assert_awaited_once()

    async def test_success_transaction_cannot_be_deleted(self):
        payment = Payment(
            id=uuid.uuid4(), order_id=uuid.uuid4(), provider="midtrans",
            gross_amount=100, currency="IDR", transaction_status="success",
        )
        session = AsyncMock()
        session.get.return_value = payment

        with self.assertRaises(ConflictException) as caught:
            await PaymentService.delete_transaction(session, payment.id, uuid.uuid4())

        self.assertEqual("PAYMENT_DELETE_FORBIDDEN", caught.exception.code)
        session.commit.assert_not_awaited()

    def test_bulk_contract_rejects_duplicate_ids(self):
        payment_id = uuid.uuid4()
        with self.assertRaises(ValueError):
            TransactionBulkActionRequest(
                payment_ids=[payment_id, payment_id], action="canceled"
            )

    def test_british_cancelled_is_rejected_for_payment_contract(self):
        with self.assertRaises(ValueError):
            TransactionStatusUpdateRequest(status="cancelled")

    async def test_bulk_action_rolls_back_everything_when_one_item_conflicts(self):
        first_id, second_id = uuid.uuid4(), uuid.uuid4()
        payload = TransactionBulkActionRequest(
            payment_ids=[first_id, second_id], action="success"
        )
        session = AsyncMock()
        order = MagicMock()
        payment = MagicMock()
        effect = [
            (order, payment),
            ConflictException("INVALID_PAYMENT_STATUS_TRANSITION", "not allowed"),
        ]

        with patch.object(PaymentService, "update_transaction_status", AsyncMock(side_effect=effect)):
            with self.assertRaises(ConflictException):
                await PaymentService.bulk_transaction_action(session, payload, uuid.uuid4())

        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
