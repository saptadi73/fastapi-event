import asyncio
import json
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import ConflictException, ValidationException
from app.modules.events.models import Event
from app.modules.participants.models import ParticipantProfile
from app.modules.payments import schemas
from app.modules.payments.doku import DokuCheckoutClient
from app.modules.payments.models import Order, OrderStatus, Payment, PaymentStatus
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.service import PaymentService
from app.modules.users.models import User


class DokuCheckoutTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.order = Order(id=uuid.uuid4(), user_id=uuid.uuid4(), event_id=uuid.uuid4(),
                           order_number="CHECKOUT-TEST", currency="IDR", total_amount=Decimal("20000000"),
                           status=OrderStatus.PENDING)
        self.payments = []
        self.committed = []
        self.lock = asyncio.Lock()
        self.sessions = []
        self.settings = SimpleNamespace(QRIS_SEGMENT_LIMIT_IDR=9000000,
                                        DOKU_PAYMENT_DUE_MINUTES=60, DOKU_CALLBACK_URL="https://event.test/status")
        self.response = {"response": {"payment": {"url": "https://checkout.doku.com/test"}}}
        self.client = AsyncMock(side_effect=self.provider_response)
        patches = [
            patch("app.modules.payments.service.get_settings", return_value=self.settings),
            patch.object(PaymentRepository, "get_registrations_for_user", AsyncMock(return_value=[])),
            patch.object(PaymentRepository, "get_order_for_user", AsyncMock(side_effect=self.owned_order)),
            patch.object(PaymentRepository, "get_payments_by_order", AsyncMock(side_effect=lambda *a, **kw: list(self.payments))),
            patch.object(PaymentService, "_payment_progress", AsyncMock(side_effect=self.progress)),
            patch.object(DokuCheckoutClient, "_credentials"),
            patch.object(DokuCheckoutClient, "create_payment", self.client),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    async def asyncTearDown(self):
        for session in self.sessions:
            await session.rollback()

    def session(self):
        session = MagicMock()
        session.holds_order_lock = False
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        async def release():
            if session.holds_order_lock:
                session.holds_order_lock = False
                self.lock.release()
        async def commit():
            self.committed[:] = [(p.id, p.provider_order_id, p.external_id) for p in self.payments]
            await release()
        session.commit = AsyncMock(side_effect=commit)
        session.rollback = AsyncMock(side_effect=release)
        def add(payment):
            payment.id = payment.id or uuid.uuid4()
            self.payments.append(payment)
        session.add.side_effect = add
        async def get(model, key, **kwargs):
            if model is User:
                return SimpleNamespace(id=key, full_name="Test", email="test@example.invalid", phone="")
            if model is Event:
                return SimpleNamespace(id=key, name="Event")
            if model is ParticipantProfile:
                return SimpleNamespace(id=key, user_id=self.order.user_id, full_name="Test")
            return self.order
        session.get = AsyncMock(side_effect=get)
        self.sessions.append(session)
        return session

    async def owned_order(self, session, order_id, user_id, *, lock=False):
        self.assertTrue(lock, "Checkout must request the repository's PostgreSQL row lock")
        if not session.holds_order_lock:
            await self.lock.acquire()
            session.holds_order_lock = True
        return self.order

    async def progress(self, *args):
        paid = sum((Decimal(str(p.gross_amount)) for p in self.payments if p.transaction_status == "success"), Decimal("0"))
        return paid, max(Decimal(str(self.order.total_amount)) - paid, Decimal("0"))

    async def provider_response(self, body, *, request_id):
        payment = self.payments[-1]
        self.assertIn((payment.id, body["order"]["invoice_number"], request_id), self.committed)
        self.assertEqual(payment.provider_transaction_id, request_id)
        self.assertEqual(payment.transaction_status, "created")
        self.assertNotIn("payment_method_types", body["payment"])
        return self.response, request_id

    async def checkout(self, session=None):
        return await PaymentService.create_doku_checkout(
            session or self.session(), schemas.CreateDokuCheckoutRequest(order_id=self.order.id), self.order.user_id)

    def existing(self, **kwargs):
        defaults = dict(id=uuid.uuid4(), order_id=self.order.id, provider="doku", currency="IDR",
                        gross_amount=9000000, transaction_status="pending", payment_type="doku_checkout",
                        payment_sequence=1, payment_sequence_count=3)
        defaults.update(kwargs)
        payment = Payment(**defaults)
        self.payments.append(payment)
        return payment

    async def test_split_all_methods_and_continue_exact_balance(self):
        for sequence, amount in [(1, 9000000), (2, 9000000), (3, 2000000)]:
            result, _ = await self.checkout()
            self.assertEqual((sequence, 3, amount), (result.payment_sequence, result.payment_sequence_count, result.payment_amount))
            self.payments[-1].transaction_status = "success"
            self.order.status = "partially_paid"
        self.assertEqual(self.client.await_count, 3)

    async def test_exact_limit_and_one_rupiah_above(self):
        self.order.total_amount = Decimal("9000000")
        result, _ = await self.checkout()
        self.assertEqual((1, 9000000), (result.payment_sequence_count, result.payment_amount))
        self.payments.clear()
        self.order.total_amount = Decimal("9000001")
        result, _ = await self.checkout()
        self.assertEqual((2, 9000000), (result.payment_sequence_count, result.payment_amount))

    async def test_concurrent_request_sees_committed_attempt_and_does_not_call_doku(self):
        entered, finish = asyncio.Event(), asyncio.Event()
        async def slow(body, *, request_id):
            await self.provider_response(body, request_id=request_id)
            entered.set()
            await finish.wait()
            return self.response, request_id
        self.client.side_effect = slow
        first = asyncio.create_task(self.checkout())
        await asyncio.wait_for(entered.wait(), 2)
        second_session = self.session()
        try:
            with self.assertRaises(ConflictException):
                await asyncio.wait_for(self.checkout(second_session), 2)
        finally:
            await second_session.rollback()
            finish.set()
            await first
        self.assertEqual(len(self.payments), 1)
        self.assertEqual(self.client.await_count, 1)

    async def test_timeout_then_retry_keeps_one_durable_invoice(self):
        async def timeout(body, *, request_id):
            await self.provider_response(body, request_id=request_id)
            raise ValidationException("DOKU_UNAVAILABLE", "timeout")
        self.client.side_effect = timeout
        session = self.session()
        with self.assertRaises(ValidationException):
            await self.checkout(session)
        await session.rollback()
        with self.assertRaises(ConflictException):
            await self.checkout()
        self.assertEqual(self.client.await_count, 1)
        self.assertEqual(len(self.committed), 1)
        self.assertEqual(self.payments[0].transaction_status, "created")

    async def test_pending_legacy_and_other_provider_attempts_block_checkout(self):
        for provider, method in [("doku", "doku_snap_va"), ("doku_snap_qris", "doku_snap_qris"), ("midtrans", "qris")]:
            self.payments.clear()
            self.existing(provider=provider, payment_type=method)
            session = self.session()
            with self.assertRaises(ConflictException):
                await self.checkout(session)
            await session.rollback()
        self.client.assert_not_awaited()

    async def test_expired_local_url_still_blocks_until_reconciled(self):
        payment = self.existing(checkout_url="https://checkout.doku.com/old", expired_at=datetime.now(timezone.utc) - timedelta(minutes=1))
        with self.assertRaises(ConflictException):
            await self.checkout()
        self.assertEqual(payment.transaction_status, "pending")
        self.client.assert_not_awaited()

    async def test_reuses_legacy_hosted_url_and_actual_amount(self):
        payment = self.existing(payment_type=None, gross_amount=5000000, checkout_url="https://checkout.doku.com/old",
                                expired_at=datetime.now(timezone.utc) + timedelta(minutes=5))
        result, _ = await self.checkout()
        self.assertEqual(result.payment_id, payment.id)
        self.assertEqual(result.payment_amount, 5000000)
        self.client.assert_not_awaited()

    async def test_retry_after_verified_expiry_uses_new_invoice_same_sequence(self):
        self.existing(transaction_status="expired", provider_order_id="OLD-INVOICE")
        result, _ = await self.checkout()
        self.assertEqual(result.payment_sequence, 1)
        self.assertNotEqual(self.payments[-1].provider_order_id, "OLD-INVOICE")

    async def test_legacy_settlement_amount_caps_remaining_balance(self):
        self.existing(transaction_status="success", gross_amount=15000000, payment_sequence=1)
        self.order.status = "partially_paid"
        result, _ = await self.checkout()
        self.assertEqual((2, 2, 5000000), (result.payment_sequence, result.payment_sequence_count, result.payment_amount))

    async def test_success_during_provider_request_is_not_downgraded(self):
        async def paid(body, *, request_id):
            await self.provider_response(body, request_id=request_id)
            self.payments[-1].transaction_status = "success"
            self.order.status = "paid"
            return self.response, request_id
        self.client.side_effect = paid
        result, _ = await self.checkout()
        self.assertEqual(self.payments[-1].transaction_status, "success")
        self.assertTrue(result.already_paid)
        self.assertFalse(result.requires_payment)
        self.assertEqual(result.payment_url, "")

    async def test_missing_provider_url_remains_reserved(self):
        self.response = {"response": {"payment": {}}}
        with self.assertRaises(ValidationException):
            await self.checkout()
        with self.assertRaises(ConflictException):
            await self.checkout()
        self.assertEqual(self.client.await_count, 1)

    async def test_non_idr_order_is_rejected_before_provider_request(self):
        self.order.currency = "USD"
        with self.assertRaises(ValidationException):
            await self.checkout()
        self.client.assert_not_awaited()

    async def test_multiple_active_attempts_never_resume_an_arbitrary_one(self):
        for _ in range(2):
            self.existing(checkout_url="https://checkout.doku.com/old", expired_at=datetime.now(timezone.utc) + timedelta(minutes=5))
        with self.assertRaises(ConflictException):
            await self.checkout()
        self.client.assert_not_awaited()

    async def test_configuration_cannot_raise_the_nine_million_cap(self):
        self.settings.QRIS_SEGMENT_LIMIT_IDR = 20000000
        result, _ = await self.checkout()
        self.assertEqual(result.payment_amount, 9000000)

    async def test_invalid_limit_is_rejected_without_reservation(self):
        for limit in [0, -1, float("nan")]:
            self.settings.QRIS_SEGMENT_LIMIT_IDR = limit
            session = self.session()
            with self.assertRaises(ValidationException):
                await self.checkout(session)
            session.commit.assert_not_awaited()
            await session.rollback()
        self.client.assert_not_awaited()

    async def test_expired_order_is_rejected_without_provider_call(self):
        self.order.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        with self.assertRaises(ConflictException):
            await self.checkout()
        self.client.assert_not_awaited()

    async def test_legacy_registration_route_also_locks_order(self):
        registration = SimpleNamespace(id=uuid.uuid4(), participant_id=uuid.uuid4(), event_id=self.order.event_id)
        session = self.session()
        with (
            patch.object(PaymentRepository, "get_registrations_for_user", AsyncMock(return_value=[registration])),
            patch.object(PaymentRepository, "get_latest_order", AsyncMock(return_value=self.order)),
        ):
            result, _ = await PaymentService.create_doku_checkout(session,
                schemas.CreateDokuCheckoutRequest(registration_id=registration.id), self.order.user_id)
        session.get.assert_any_await(User, self.order.user_id, with_for_update={"key_share": True})
        self.assertEqual(result.payment_amount, 9000000)


class DokuRequestIdentityTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_uses_reserved_request_id(self):
        client = DokuCheckoutClient()
        client.settings = SimpleNamespace(DOKU_CLIENT_ID="test", DOKU_SECRET_KEY="secret", DOKU_BASE_URL="https://api-sandbox.doku.com", DOKU_CHECKOUT_PATH="/checkout/v1/payment")
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.headers = {}
        response.read.return_value = b'{"payment":{"url":"https://checkout.doku.com/test"}}'
        with patch("app.modules.payments.doku.urlopen", return_value=response) as send:
            _, request_id = await client.create_payment({"order": {"invoice_number": "reserved-invoice"}}, request_id="reserved-request")
        self.assertEqual(request_id, "reserved-request")
        self.assertEqual(send.call_args.args[0].get_header("Request-id"), request_id)


class DokuNotificationStateTests(unittest.IsolatedAsyncioTestCase):
    async def test_checkout_failures_and_late_notifications_preserve_state(self):
        for initial, incoming, expected, method in [
            ("created", "FAILED", "pending", "doku_checkout"),
            ("pending", "TIMEOUT", "pending", "doku_checkout"),
            ("pending", "REDIRECT", "pending", None),
            ("success", "FAILED", "success", "doku_checkout"),
            ("success", "EXPIRED", "success", "doku_checkout"),
            ("success", "PENDING", "success", "doku_checkout"),
            ("pending", "FAILED", "failed", "doku_snap_va"),
            ("pending", "EXPIRED", "expired", "doku_checkout"),
        ]:
            with self.subTest(initial=initial, incoming=incoming, method=method):
                payment = Payment(id=uuid.uuid4(), order_id=uuid.uuid4(), provider="doku", payment_type=method,
                                  gross_amount=9000000, transaction_status=initial)
                order = Order(id=payment.order_id, status="pending")
                session = AsyncMock()
                session.add = MagicMock()
                session.get.return_value = order
                settings = SimpleNamespace(DOKU_CLIENT_ID="client", DOKU_SECRET_KEY="secret", DOKU_NOTIFICATION_PATH="/webhook")
                with (
                    patch("app.modules.payments.service.get_settings", return_value=settings),
                    patch("app.modules.payments.service.verify_signature", return_value=True),
                    patch.object(PaymentRepository, "get_webhook_event", AsyncMock(return_value=None)),
                    patch.object(PaymentRepository, "get_payment_by_provider_order_id", AsyncMock(return_value=payment)),
                    patch.object(PaymentService, "_reconcile_order_payment", AsyncMock(return_value=(0, 9000000, False))),
                    patch.object(PaymentService, "_notify_payment_status", AsyncMock()),
                ):
                    await PaymentService.handle_doku_notification(session, json.dumps({
                        "order": {"invoice_number": "invoice", "amount": 9000000}, "transaction": {"status": incoming},
                    }).encode(), {"client-id": "client", "request-id": str(uuid.uuid4()), "request-timestamp": "now", "signature": "signature"})
                self.assertEqual(payment.transaction_status, expected)
