import unittest
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import ValidationError
from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.modules.payments import doku_order as pilot


class DokuOrderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.order = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), order_number="TEST-ORDER", status="pending", currency="IDR", expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        self.user = SimpleNamespace(id=self.order.user_id, full_name="Test User", email="test@example.invalid", phone="")
        self.db = MagicMock()
        self.db.flush = AsyncMock()
        self.db.commit = AsyncMock()
        self.db.refresh = AsyncMock()
        self.db.add.side_effect = lambda payment: setattr(payment, "id", uuid.uuid4())
        self.patches = [
            patch.object(pilot, "owned_order", AsyncMock(return_value=self.order)),
            patch.object(pilot, "active_payment", AsyncMock(return_value=None)),
            patch.object(pilot, "capabilities", AsyncMock(return_value={"virtual_accounts": list(pilot.BANKS), "qris": True, "credit_card": True})),
            patch.object(pilot.PaymentService, "_next_payment_segment", AsyncMock(return_value=(1, 2, Decimal("9000000")))),
            patch.object(pilot.PaymentService, "_payment_progress", AsyncMock(return_value=(Decimal("0"), Decimal("9900000")))),
            patch.object(pilot.DokuSnapClient, "create_va", AsyncMock(return_value=({"virtualAccountData": {"virtualAccountNo": "123456789"}}, "va-request"))),
            patch.object(pilot.DokuSnapClient, "create_qris", AsyncMock(return_value=({"qrContent": "provider-qr-content"}, "qr-request"))),
            patch.object(pilot.DokuCheckoutClient, "create_payment", AsyncMock(return_value=({"response": {"payment": {"url": "https://checkout.doku.com/card"}}}, "card-request"))),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    async def test_va_uses_remaining_server_amount_and_selected_bank(self):
        data = await pilot.create_payment(self.db, self.order.id, pilot.DokuOrderChoice(method="virtual_account", bank_code="BCA"), self.user)
        args = pilot.DokuSnapClient.create_va.call_args.args
        self.assertEqual(args[0], "BCA")
        self.assertEqual(args[1]["totalAmount"]["value"], "9900000.00")
        self.assertEqual(data["virtual_account_no"], "123456789")
        self.assertEqual(data["order_id"], str(self.order.id))
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["payment_sequence_count"], 1)
        pilot.DokuCheckoutClient.create_payment.assert_not_called()

    async def test_qris_uses_segment_and_exact_provider_content(self):
        data = await pilot.create_payment(self.db, self.order.id, pilot.DokuOrderChoice(method="qris"), self.user)
        self.assertEqual(data["amount"], 9000000)
        self.assertEqual(data["qr_content"], "provider-qr-content")
        self.assertEqual(data["payment_sequence_count"], 2)
        self.assertEqual(self.order.status, "pending")

    async def test_card_checkout_is_restricted_to_card(self):
        data = await pilot.create_payment(self.db, self.order.id, pilot.DokuOrderChoice(method="credit_card"), self.user)
        body = pilot.DokuCheckoutClient.create_payment.call_args.args[0]
        self.assertEqual(body["payment"]["payment_method_types"], ["CREDIT_CARD"])
        self.assertEqual(body["additional_info"]["order_id"], str(self.order.id))
        self.assertEqual(data["payment_url"], "https://checkout.doku.com/card")

    async def test_methods_use_expected_amounts_at_split_boundaries(self):
        for total in (Decimal("8999999"), Decimal("9000000"), Decimal("9000001"), Decimal("27000000")):
            for method in ("qris", "virtual_account", "credit_card"):
                with self.subTest(total=total, method=method):
                    plan = pilot.PaymentService._segment_plan(total)
                    pilot.PaymentService._next_payment_segment.return_value = (1, len(plan), plan[0])
                    pilot.PaymentService._payment_progress.return_value = (Decimal("0"), total)
                    choice = pilot.DokuOrderChoice(method=method, bank_code="BCA" if method == "virtual_account" else None)
                    data = await pilot.create_payment(self.db, self.order.id, choice, self.user)
                    expected = plan[0] if method == "qris" else total
                    self.assertEqual(data["amount"], expected)
                    self.assertEqual(data["payment_sequence_count"], len(plan) if method == "qris" else 1)
                    if method == "credit_card":
                        body = pilot.DokuCheckoutClient.create_payment.call_args.args[0]
                        self.assertEqual(body["order"]["amount"], total)
                        self.assertIn("(1/1)", body["order"]["line_items"][0]["name"])

    async def test_non_qris_collects_full_remaining_balance_after_partial_payment(self):
        self.order.status = "partially_paid"
        pilot.PaymentService._next_payment_segment.return_value = (2, 3, Decimal("9000000"))
        pilot.PaymentService._payment_progress.return_value = (Decimal("9000000"), Decimal("18000000"))
        for method in ("virtual_account", "credit_card"):
            with self.subTest(method=method):
                choice = pilot.DokuOrderChoice(method=method, bank_code="BCA" if method == "virtual_account" else None)
                data = await pilot.create_payment(self.db, self.order.id, choice, self.user)
                self.assertEqual(data["amount"], 18000000)
                self.assertEqual(data["payment_sequence"], 2)
                self.assertEqual(data["payment_sequence_count"], 2)
                self.assertEqual(self.order.status, "partially_paid")

    async def test_disabled_channel_never_calls_gateway(self):
        pilot.capabilities.return_value["qris"] = False
        with self.assertRaises(ValidationException):
            await pilot.create_payment(self.db, self.order.id, pilot.DokuOrderChoice(method="qris"), self.user)
        pilot.DokuSnapClient.create_qris.assert_not_called()
        self.db.add.assert_not_called()

    async def test_paid_and_expired_orders_never_call_gateway(self):
        for status in ("paid", "canceled", "expired"):
            self.order.status = status
            with self.assertRaises(ConflictException):
                await pilot.create_payment(self.db, self.order.id, pilot.DokuOrderChoice(method="qris"), self.user)
        self.order.status = "pending"
        self.order.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        with self.assertRaises(ConflictException):
            await pilot.create_payment(self.db, self.order.id, pilot.DokuOrderChoice(method="qris"), self.user)
        pilot.DokuSnapClient.create_qris.assert_not_called()

    async def test_active_va_is_reused_without_second_request(self):
        await pilot.create_payment(self.db, self.order.id, pilot.DokuOrderChoice(method="virtual_account", bank_code="BCA"), self.user)
        payment = self.db.add.call_args.args[0]
        pilot.active_payment.return_value = payment
        data = await pilot.create_payment(self.db, self.order.id, pilot.DokuOrderChoice(method="virtual_account", bank_code="BCA"), self.user)
        self.assertEqual(data["payment_id"], str(payment.id))
        pilot.DokuSnapClient.create_va.assert_awaited_once()
        with self.assertRaises(ConflictException):
            await pilot.create_payment(self.db, self.order.id, pilot.DokuOrderChoice(method="virtual_account", bank_code="BNI"), self.user)
        pilot.DokuSnapClient.create_va.assert_awaited_once()

    async def test_midtrans_pending_blocks_doku(self):
        pilot.active_payment.return_value = SimpleNamespace(payment_type="midtrans")
        with self.assertRaises(ConflictException):
            await pilot.create_payment(self.db, self.order.id, pilot.DokuOrderChoice(method="qris"), self.user)
        pilot.DokuSnapClient.create_qris.assert_not_called()

    async def test_timeout_retains_attempt_and_blocks_duplicate(self):
        async def timeout(*args):
            self.db.commit.assert_awaited_once()
            raise TimeoutError("Uncertain provider response")
        pilot.DokuSnapClient.create_qris.side_effect = timeout
        with self.assertRaises(TimeoutError):
            await pilot.create_payment(self.db, self.order.id, pilot.DokuOrderChoice(method="qris"), self.user)
        payment = self.db.add.call_args.args[0]
        self.assertEqual(payment.transaction_status, "created")
        pilot.active_payment.return_value = payment
        with self.assertRaises(ConflictException):
            await pilot.create_payment(self.db, self.order.id, pilot.DokuOrderChoice(method="qris"), self.user)
        pilot.DokuSnapClient.create_qris.assert_awaited_once()

    async def test_other_users_order_is_rejected(self):
        pilot.owned_order.side_effect = NotFoundException("ORDER_NOT_FOUND", "Missing")
        with self.assertRaises(NotFoundException):
            await pilot.create_payment(self.db, uuid.uuid4(), pilot.DokuOrderChoice(method="qris"), self.user)
        self.db.add.assert_not_called()

    def test_client_cannot_supply_amount_or_card_data(self):
        for extra in ({"amount": 1}, {"card_number": "1234"}, {"cvv": "123"}):
            with self.assertRaises(ValidationError):
                pilot.DokuOrderChoice(method="credit_card", **extra)
        for choice in ({"method": "virtual_account"}, {"method": "qris", "bank_code": "BCA"}, {"method": "virtual_account", "bank_code": "OTHER"}):
            with self.assertRaises(ValidationError):
                pilot.DokuOrderChoice(**choice)


if __name__ == "__main__":
    unittest.main()
