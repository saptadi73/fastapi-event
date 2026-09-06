import base64
import hashlib
import hmac
import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.modules.payments.doku import canonical_json, generate_signature
from app.modules.payments.doku_inquiry import INQUIRY_PATH, handle_inquiry


class InquiryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.settings = SimpleNamespace(DOKU_CLIENT_ID="merchant", DOKU_SECRET_KEY="test-secret")
        self.payload = {"service": {"id": "VIRTUAL_ACCOUNT"}, "acquirer": {"id": "BRI"},
                        "channel": {"id": "VIRTUAL_ACCOUNT_BRI"},
                        "virtual_account_info": {"virtual_account_number": "123626000001", "billing_type": "FIX_BILL"},
                        "virtual_account_inquiry": {"date": "20260906100120"}}
        self.payment = SimpleNamespace(transaction_status="pending", expired_at=None,
                                       gross_amount=150000, currency="IDR", provider_order_id="INV-PART-1")
        self.order = SimpleNamespace(status="pending", expires_at=None, currency="IDR")
        self.user = SimpleNamespace(full_name="Test Customer")
        self.session = AsyncMock()
        self.result = MagicMock()
        self.result.all.return_value = [(self.payment, self.order, self.user)]
        self.session.execute.return_value = self.result

    async def call(self, payload=None, stale=False, tamper=False):
        body = canonical_json(payload if payload is not None else self.payload)
        timestamp = (datetime.now(timezone.utc) - timedelta(hours=1 if stale else 0)).strftime("%Y-%m-%dT%H:%M:%SZ")
        headers = {"client-id": "merchant", "request-id": "inquiry-1", "request-timestamp": timestamp,
                   "signature": generate_signature("merchant", "inquiry-1", timestamp, INQUIRY_PATH, body, "test-secret")}
        return await handle_inquiry(self.session, body + (b" " if tamper else b""), headers, self.settings, INQUIRY_PATH)

    async def test_success_signed_response_and_no_mutations(self):
        response = await self.call()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.body)["order"], {"invoice_number": "INV-PART-1", "amount": 150000})
        component = "\n".join(["Client-Id:merchant", "Request-Id:inquiry-1",
            "Response-Timestamp:" + response.headers["response-timestamp"], "Request-Target:" + INQUIRY_PATH,
            "Digest:" + base64.b64encode(hashlib.sha256(response.body).digest()).decode()])
        expected = "HMACSHA256=" + base64.b64encode(hmac.new(b"test-secret", component.encode(), hashlib.sha256).digest()).decode()
        self.assertEqual(response.headers["signature"], expected)
        self.session.commit.assert_not_called()
        query = str(self.session.execute.call_args.args[0])
        for field in ("payments.provider", "payments.channel_code", "payments.virtual_account_no", "payments.deleted_at"):
            self.assertIn(field, query)

    async def test_bad_signature_and_stale_request_do_not_query_database(self):
        for kwargs in ({"tamper": True}, {"stale": True}):
            self.assertEqual((await self.call(**kwargs)).status_code, 401)
        self.session.execute.assert_not_called()

    async def test_missing_and_ambiguous_va(self):
        for rows, code, status in [([], 404, "billing_not_found"),
                ([(self.payment, self.order, self.user)] * 2, 400, "decline")]:
            self.result.all.return_value = rows
            response = await self.call()
            self.assertEqual(response.status_code, code)
            self.assertEqual(json.loads(response.body)["virtual_account_inquiry"]["status"], status)
            self.assertIn("signature", response.headers)

    async def test_paid_expired_canceled_and_fractional_amount(self):
        for state, expected in [("success", "billing_already_paid"), ("expired", "billing_was_expired"), ("canceled", "decline")]:
            self.payment.transaction_status = state
            self.assertEqual(json.loads((await self.call()).body)["virtual_account_inquiry"]["status"], expected)
        self.payment.transaction_status = "pending"
        self.payment.gross_amount = "100.50"
        self.assertEqual((await self.call()).status_code, 400)

    async def test_invalid_payload_declined_before_lookup(self):
        for payload in ([], {}, {**self.payload, "acquirer": {"id": "BCA"}},
                        {**self.payload, "virtual_account_info": {"virtual_account_number": "123", "billing_type": "NO_BILL"}}):
            self.assertEqual((await self.call(payload)).status_code, 400)
        self.session.execute.assert_not_called()

    async def test_elapsed_expiration_and_partial_order(self):
        self.order.status = "partially_paid"
        self.assertEqual((await self.call()).status_code, 200)
        self.order.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.assertEqual(json.loads((await self.call()).body)["virtual_account_inquiry"]["status"], "billing_was_expired")
