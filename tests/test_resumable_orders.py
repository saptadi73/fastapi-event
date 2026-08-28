import unittest
import uuid
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.dialects import postgresql

from app.core.exceptions import ConflictException
from app.main import app
from app.modules.payments import schemas
from app.modules.payments.models import Order, OrderStatus, Payment, PaymentStatus, order_allowed_actions
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.service import PaymentService


def make_order(status=OrderStatus.PENDING, canceled_by=None):
    return Order(
        id=uuid.uuid4(), user_id=uuid.uuid4(), event_id=uuid.uuid4(), registration_id=None,
        order_number="ORD-RESUMABLE", subtotal=100000, discount_amount=0,
        tax_amount=0, service_fee=0, total_amount=100000, currency="IDR",
        status=status, canceled_by=canceled_by,
    )


class ResumableOrderContractTests(unittest.TestCase):
    def test_order_allowed_actions_are_backend_driven(self):
        for status in (OrderStatus.DRAFT, OrderStatus.PENDING, OrderStatus.EXPIRED):
            self.assertEqual(["continue_payment", "cancel"], order_allowed_actions(status))
        self.assertEqual(["continue_payment", "cancel"], order_allowed_actions(OrderStatus.CANCELED))
        self.assertEqual([], order_allowed_actions(OrderStatus.CANCELED, uuid.uuid4()))
        self.assertEqual([], order_allowed_actions(OrderStatus.PAID))

    def test_resumable_order_routes_are_registered(self):
        paths = app.openapi()["paths"]
        self.assertIn("get", paths["/api/v1/orders"])
        self.assertIn("get", paths["/api/v1/orders/{order_id}/detail"])
        self.assertIn("post", paths["/api/v1/orders/{order_id}/continue-payment"])
        self.assertIn("delete", paths["/api/v1/orders/{order_id}"])

    def test_doku_url_is_reused_only_before_expiry(self):
        now = datetime.now(timezone.utc)
        payment = Payment(
            order_id=uuid.uuid4(), provider="doku", gross_amount=100000,
            currency="IDR", transaction_status=PaymentStatus.PENDING,
            checkout_url="https://checkout.doku.test/123", expired_at=now + timedelta(minutes=5),
        )
        self.assertEqual(payment.checkout_url, PaymentService._reusable_doku_checkout_url(payment, now))
        payment.expired_at = now - timedelta(seconds=1)
        self.assertEqual("", PaymentService._reusable_doku_checkout_url(payment, now))


class ResumableOrderServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_order_lock_targets_only_order_table_with_outer_ownership_joins(self):
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result

        await PaymentRepository.get_order_for_user(
            session, uuid.uuid4(), uuid.uuid4(), lock=True
        )

        statement = session.execute.await_args.args[0]
        sql = str(statement.compile(dialect=postgresql.dialect())).lower()
        self.assertIn("for update of orders", sql)

    async def test_cancel_pending_order_soft_cancels_active_attempt(self):
        actor_id = uuid.uuid4()
        order = make_order()
        order.user_id = actor_id
        payment = Payment(
            id=uuid.uuid4(), order_id=order.id, provider="midtrans", gross_amount=100000,
            currency="IDR", transaction_status=PaymentStatus.PENDING,
        )
        session = AsyncMock()
        session.add = MagicMock()
        detail = MagicMock()
        with (
            patch.object(PaymentRepository, "get_order_for_user", AsyncMock(return_value=order)),
            patch.object(PaymentRepository, "get_payments_by_order", AsyncMock(return_value=[payment])),
            patch.object(PaymentService, "_user_order_detail", AsyncMock(return_value=detail)),
        ):
            result = await PaymentService.cancel_user_order(
                session, order.id, actor_id, "Tidak jadi melanjutkan"
            )

        self.assertIs(detail, result)
        self.assertEqual(OrderStatus.CANCELED, order.status)
        self.assertEqual(actor_id, order.canceled_by)
        self.assertEqual(PaymentStatus.CANCELED, payment.transaction_status)
        self.assertEqual([], order.allowed_actions)
        session.commit.assert_awaited_once()
        self.assertEqual("CANCELED", session.add.call_args.args[0].event_status)

    async def test_paid_order_cannot_be_canceled(self):
        order = make_order(OrderStatus.PAID)
        session = AsyncMock()
        with (
            patch.object(PaymentRepository, "get_order_for_user", AsyncMock(return_value=order)),
            patch.object(PaymentRepository, "get_payments_by_order", AsyncMock(return_value=[])),
        ):
            with self.assertRaises(ConflictException) as caught:
                await PaymentService.cancel_user_order(session, order.id, order.user_id)
        self.assertEqual("PAID_ORDER_CANCEL_FORBIDDEN", caught.exception.code)

    async def test_legacy_gateway_canceled_order_can_continue_without_rebuilding_cart(self):
        order = make_order(OrderStatus.CANCELED, canceled_by=None)
        stale = Payment(
            id=uuid.uuid4(), order_id=order.id, provider="doku", gross_amount=100000,
            currency="IDR", transaction_status=PaymentStatus.FAILED,
        )
        checkout = schemas.DokuCheckoutResponse(
            payment_url="https://checkout.doku.test/new", payment_id=uuid.uuid4(),
            order_status=OrderStatus.PENDING,
        )
        session = AsyncMock()
        with (
            patch.object(PaymentRepository, "get_order_for_user", AsyncMock(return_value=order)),
            patch.object(PaymentRepository, "get_payments_by_order", AsyncMock(return_value=[stale])),
            patch.object(PaymentService, "create_doku_checkout", AsyncMock(return_value=(checkout, order))) as create_checkout,
        ):
            response, returned_order = await PaymentService.continue_user_order_payment(
                session, order.id, order.user_id, "doku"
            )

        self.assertIs(checkout, response)
        self.assertIs(order, returned_order)
        self.assertEqual(OrderStatus.PENDING, order.status)
        create_checkout.assert_awaited_once()
        session.flush.assert_awaited_once()

    async def test_failed_doku_webhook_keeps_order_payable(self):
        order = make_order(OrderStatus.PENDING)
        payment = Payment(
            id=uuid.uuid4(), order_id=order.id, provider="doku", gross_amount=100000,
            currency="IDR", transaction_status=PaymentStatus.PENDING,
        )
        body = json.dumps({
            "order": {"invoice_number": order.order_number, "amount": 100000},
            "transaction": {"status": "FAILED"},
        }).encode()
        headers = {
            "client-id": "client", "request-id": "request-1",
            "request-timestamp": "2026-08-28T00:00:00Z", "signature": "signature",
        }
        session = AsyncMock()
        session.add = MagicMock()
        settings = MagicMock(DOKU_CLIENT_ID="client", DOKU_SECRET_KEY="secret", DOKU_NOTIFICATION_PATH="/webhook")
        with (
            patch("app.modules.payments.service.get_settings", return_value=settings),
            patch("app.modules.payments.service.verify_signature", return_value=True),
            patch.object(PaymentRepository, "get_webhook_event", AsyncMock(return_value=None)),
            patch.object(PaymentRepository, "get_order_by_number", AsyncMock(return_value=order)),
            patch.object(PaymentRepository, "get_payment_by_order", AsyncMock(return_value=payment)),
            patch.object(PaymentService, "_notify_payment_status", AsyncMock()),
        ):
            result = await PaymentService.handle_doku_notification(session, body, headers)

        self.assertEqual("failed", result)
        self.assertEqual(OrderStatus.PENDING, order.status)
        self.assertEqual(PaymentStatus.FAILED, payment.transaction_status)
        session.commit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
