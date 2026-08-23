import hashlib
import unittest
from unittest.mock import patch

from app.core.config import Settings
from app.modules.payments.midtrans import (
    MidtransClient, normalize_midtrans_channel, verify_notification_signature,
    verify_pay_account_signature,
)


class MidtransSecurityTests(unittest.TestCase):
    def test_notification_signature_is_verified_constant_time(self):
        payload = {
            "order_id": "ORD-123",
            "status_code": "200",
            "gross_amount": "10000.00",
        }
        payload["signature_key"] = hashlib.sha512(
            b"ORD-12320010000.00server-secret"
        ).hexdigest()

        self.assertTrue(verify_notification_signature(payload, "server-secret"))
        payload["gross_amount"] = "99999.00"
        self.assertFalse(verify_notification_signature(payload, "server-secret"))

    def test_environment_selects_midtrans_hosts(self):
        with patch("app.modules.payments.midtrans.get_settings", return_value=Settings(MIDTRANS_IS_PRODUCTION=False)):
            client = MidtransClient()
            self.assertIn("sandbox", client.snap_base_url)
            self.assertIn("sandbox", client.api_base_url)
        with patch("app.modules.payments.midtrans.get_settings", return_value=Settings(MIDTRANS_IS_PRODUCTION=True)):
            client = MidtransClient()
            self.assertNotIn("sandbox", client.snap_base_url)

    def test_pay_account_signature_uses_account_fields(self):
        payload = {
            "account_id": "account-123",
            "account_status": "ENABLED",
            "status_code": "200",
        }
        payload["signature_key"] = hashlib.sha512(
            b"account-123ENABLED200server-secret"
        ).hexdigest()

        self.assertTrue(verify_pay_account_signature(payload, "server-secret"))
        payload["account_status"] = "DISABLED"
        self.assertFalse(verify_pay_account_signature(payload, "server-secret"))

    def test_qris_channel_does_not_use_issuer_bank(self):
        payload = {"payment_type": "qris", "bank": "bca", "issuer": "bca", "acquirer": "gopay"}
        self.assertEqual("QRIS", normalize_midtrans_channel(payload))

    def test_virtual_account_channel_uses_bank(self):
        self.assertEqual("BCA", normalize_midtrans_channel({"payment_type": "bank_transfer", "bank": "bca"}))


if __name__ == "__main__":
    unittest.main()
