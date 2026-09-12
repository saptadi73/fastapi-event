import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from pydantic import ValidationError
from app.core.exceptions import ConflictException, NotFoundException
from app.modules.payments.models import Order, Payment
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas import DeletePaymentAttemptsRequest
from app.modules.payments.service import PaymentService


class UserPaymentCleanupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user_id = uuid4()
        self.order = Order(id=uuid4(), user_id=self.user_id, order_number="TEST", status="paid",
                           subtotal=100, discount_amount=0, tax_amount=0, service_fee=0,
                           total_amount=100, currency="IDR", order_kind="legacy")
        self.payments = [Payment(id=uuid4(), order_id=self.order.id, provider="midtrans",
                                 gross_amount=100, currency="IDR", transaction_status=status,
                                 created_at=datetime.now(timezone.utc))
                         for status in ("pending", "failed", "success")]
        self.db = AsyncMock()
        self.db.add = MagicMock()

    async def remove(self, ids, remaining=0, owner=True):
        with (
            patch.object(PaymentRepository, "get_order_for_user", AsyncMock(return_value=self.order if owner else None)),
            patch.object(PaymentRepository, "get_payments_by_order", AsyncMock(return_value=self.payments)),
            patch.object(PaymentService, "_payment_progress", AsyncMock(return_value=(Decimal(100), Decimal(remaining)))),
        ):
            return await PaymentService.delete_user_payment_attempts(self.db, self.order.id, self.user_id, ids)

    async def test_bulk_cleanup_keeps_financial_records_and_is_idempotent(self):
        ids = [payment.id for payment in self.payments[:2]]
        self.assertEqual(set(ids), set(await self.remove(ids + ids)))
        self.assertTrue(all(payment.hidden_from_user_at for payment in self.payments[:2]))
        self.assertIsNone(self.payments[2].hidden_from_user_at)
        self.assertTrue(all(payment.deleted_at is None for payment in self.payments))
        self.assertEqual(["pending", "failed", "success"], [payment.transaction_status for payment in self.payments])
        self.assertEqual("paid", self.order.status)
        self.assertEqual(2, self.db.add.call_count)
        await self.remove(ids)
        self.assertEqual(2, self.db.add.call_count)

    async def test_requires_owned_fully_paid_order(self):
        with self.assertRaises(NotFoundException):
            await self.remove([self.payments[0].id], owner=False)
        self.order.user_id = uuid4()
        with self.assertRaises(NotFoundException):
            await self.remove([self.payments[0].id])
        self.order.user_id = self.user_id
        for status, remaining in [("paid", 20), ("partially_paid", 0), ("pending", 100)]:
            self.order.status = status
            with self.assertRaises(ConflictException):
                await self.remove([self.payments[0].id], remaining=remaining)
        self.db.commit.assert_not_awaited()

    async def test_invalid_selection_is_atomic(self):
        for ids, error in [([self.payments[0].id, uuid4()], NotFoundException),
                           ([self.payments[0].id, self.payments[2].id], ConflictException)]:
            with self.assertRaises(error):
                await self.remove(ids)
            self.assertIsNone(self.payments[0].hidden_from_user_at)
        self.payments[2].transaction_status = "refunded"
        with self.assertRaises(ConflictException):
            await self.remove([self.payments[2].id])
        self.db.commit.assert_not_awaited()

    async def test_hidden_attempts_filtered_but_late_success_visible(self):
        self.payments[0].hidden_from_user_at = datetime.now(timezone.utc)
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        self.db.execute.return_value = result
        with (
            patch.object(PaymentRepository, "get_payments_by_order", AsyncMock(return_value=self.payments)),
            patch.object(PaymentService, "_payment_progress", AsyncMock(return_value=(Decimal(100), Decimal(0)))),
        ):
            detail = await PaymentService._user_order_detail(self.db, self.order)
            self.assertNotIn(self.payments[0].id, [payment.id for payment in detail.payment_attempts])
            self.assertEqual(100, detail.paid_amount)
            for status in ("success", "refunded"):
                self.payments[0].transaction_status = status
                detail = await PaymentService._user_order_detail(self.db, self.order)
                self.assertIn(self.payments[0].id, [payment.id for payment in detail.payment_attempts])

    def test_selection_bounds(self):
        for ids in ([], [uuid4() for _ in range(101)]):
            with self.assertRaises(ValidationError):
                DeletePaymentAttemptsRequest(payment_ids=ids)
