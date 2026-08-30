import base64
import hashlib
import hmac
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.modules.payments.doku_snap import (
    asymmetric_signature,
    symmetric_signature,
    verify_asymmetric_signature,
    verify_symmetric_signature,
)
from app.core.config import get_settings
from app.modules.payments.models import Order, Payment
from app.modules.payments.service import PaymentService
from app.modules.registrations.models import Registration


class DokuSnapCryptoTests(unittest.TestCase):
    def test_symmetric_signature_matches_snap_formula(self):
        payload = {"trxId": "ORD-1", "paidAmount": {"value": "10000.00", "currency": "IDR"}}
        timestamp = "2026-08-15T10:00:00+07:00"
        token = "sandbox-token"
        path = "/api/v1/webhooks/doku/snap/va/payment"
        compact = b'{"trxId":"ORD-1","paidAmount":{"value":"10000.00","currency":"IDR"}}'
        digest = hashlib.sha256(compact).hexdigest().lower()
        component = f"POST:{path}:{token}:{digest}:{timestamp}"
        expected = base64.b64encode(hmac.new(b"sandbox-secret", component.encode(), hashlib.sha512).digest()).decode()
        actual = symmetric_signature("POST", path, token, payload, timestamp, "sandbox-secret")
        self.assertEqual(expected, actual)
        self.assertTrue(verify_symmetric_signature(actual, "POST", path, token, payload, timestamp, "sandbox-secret"))
        self.assertFalse(verify_symmetric_signature(actual, "POST", path, token, payload, timestamp, "wrong"))

    def test_asymmetric_token_signature(self):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = private_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        public_pem = private_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        with tempfile.TemporaryDirectory() as directory:
            private_path = Path(directory) / "private.pem"
            public_path = Path(directory) / "public.pem"
            private_path.write_bytes(private_pem)
            public_path.write_bytes(public_pem)
            signature = asymmetric_signature("BRN-SANDBOX", "2026-08-15T10:00:00+07:00", str(private_path))
            self.assertTrue(verify_asymmetric_signature(signature, "BRN-SANDBOX", "2026-08-15T10:00:00+07:00", str(public_path)))
            self.assertFalse(verify_asymmetric_signature(signature, "OTHER", "2026-08-15T10:00:00+07:00", str(public_path)))


class DokuSnapNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_notification_marks_payment_paid_and_returns_snap_ack(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        with tempfile.TemporaryDirectory() as directory:
            private_path = Path(directory) / "merchant-private.pem"
            private_path.write_bytes(private_pem)
            settings = get_settings()
            original = {name: getattr(settings, name) for name in ("DOKU_SNAP_PARTNER_ID", "DOKU_SNAP_CLIENT_SECRET", "DOKU_SNAP_PRIVATE_KEY_PATH", "DOKU_SNAP_DOKU_CLIENT_ID")}
            settings.DOKU_SNAP_PARTNER_ID = "MERCHANT"
            settings.DOKU_SNAP_CLIENT_SECRET = "shared-secret"
            settings.DOKU_SNAP_PRIVATE_KEY_PATH = str(private_path)
            settings.DOKU_SNAP_DOKU_CLIENT_ID = "DOKU"
            try:
                order = Order(id=uuid.uuid4(), registration_id=uuid.uuid4(), order_number="ORD-TEST", total_amount=10000, subtotal=10000, currency="IDR", status="pending")
                payment = Payment(id=uuid.uuid4(), order_id=order.id, provider="doku", provider_order_id="ORD-TEST", gross_amount=10000, currency="IDR", virtual_account_no="12345", transaction_status="pending")
                registration = Registration(id=order.registration_id, event_id=uuid.uuid4(), participant_id=uuid.uuid4(), registration_number="REG-TEST", status="awaiting_payment")
                token, _ = __import__("app.modules.payments.doku_snap", fromlist=["issue_merchant_token"]).issue_merchant_token("DOKU")
                timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
                payload = {"partnerServiceId": "12345678", "customerNo": "0", "virtualAccountNo": "12345", "virtualAccountName": "Test", "trxId": "ORD-TEST", "paymentRequestId": "REQ-1", "paidAmount": {"value": "10000.00", "currency": "IDR"}}
                signature = symmetric_signature("POST", settings.DOKU_SNAP_VA_NOTIFICATION_PATH, token, payload, timestamp, "shared-secret")
                headers = {"x-timestamp": timestamp, "x-signature": signature, "x-external-id": "123456789", "x-partner-id": "DOKU", "authorization": f"Bearer {token}"}

                session = AsyncMock()
                session.add = MagicMock()
                async def get(model, identifier, **kwargs):
                    return order if model is Order else registration
                session.get.side_effect = get
                with patch("app.modules.payments.service.PaymentRepository.get_payment_by_va", AsyncMock(return_value=payment)), patch("app.modules.payments.service.PaymentRepository.get_webhook_event", AsyncMock(return_value=None)), patch("app.modules.payments.service.PaymentService._admin_user_ids", AsyncMock(return_value=[])), patch("app.modules.payments.service.PaymentService._payment_progress", AsyncMock(return_value=(10000, 0))):
                    response = await PaymentService.handle_doku_snap_va_notification(session, payload, headers)
                self.assertEqual("2002500", response["responseCode"])
                self.assertEqual("success", payment.transaction_status)
                self.assertEqual("paid", order.status)
                session.commit.assert_awaited_once()
            finally:
                for name, value in original.items():
                    setattr(settings, name, value)


if __name__ == "__main__":
    unittest.main()
