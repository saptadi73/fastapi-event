import unittest
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.modules.payments.reporting import PaymentReportingService


def payment_row(status: str, amount: str, channel: str, package_code: str = "PKG-A"):
    now = datetime(2026, 8, 17, 10, 0, tzinfo=timezone.utc)
    return {
        "payment_id": uuid.uuid4(),
        "created_at": now,
        "paid_at": now if status == "success" else None,
        "transaction_status": status,
        "payment_type": "doku_snap_va",
        "channel_code": channel,
        "gross_amount": Decimal(amount),
        "currency": "IDR",
        "provider_transaction_id": "REQ-1",
        "provider_order_id": "ORD-TEST-MT-ABC12345",
        "provider_reference_no": None,
        "virtual_account_no": "12345",
        "order_id": uuid.uuid4(),
        "order_number": "ORD-TEST",
        "order_status": "paid" if status == "success" else "pending",
        "registration_id": uuid.uuid4(),
        "registration_number": "REG-TEST",
        "event_id": uuid.uuid4(),
        "event_name": "IWBIF 2026",
        "customer_name": "Test Participant",
        "customer_email": "test@example.com",
        "package_id": uuid.uuid4(),
        "package_code": package_code,
        "package_name": "Delegate Package",
    }


class PaymentReportingTests(unittest.TestCase):
    def test_report_counts_only_success_as_revenue_and_ticket_sale(self):
        rows = [
            payment_row("success", "8000000.00", "BCA"),
            payment_row("pending", "8000000.00", "BNI"),
            payment_row("failed", "8000000.00", "BRI"),
        ]

        report = PaymentReportingService.build_report(rows, limit=2, offset=0)

        self.assertEqual(report["summary"]["total_transactions"], 3)
        self.assertEqual(report["summary"]["successful_transactions"], 1)
        self.assertEqual(report["summary"]["gross_revenue"], 8000000.0)
        self.assertEqual(report["summary"]["pending_amount"], 8000000.0)
        self.assertEqual(report["by_package"][0]["tickets_sold"], 1)
        self.assertEqual(len(report["transactions"]), 2)

    def test_csv_contains_transaction_fields(self):
        content = PaymentReportingService.csv([payment_row("success", "10000.00", "MANDIRI")])
        self.assertIn("payment_id,created_at,paid_at", content)
        self.assertIn("MANDIRI", content)
        self.assertIn("10000.0", content)
        self.assertIn("provider_order_id", content)
        self.assertIn("ORD-TEST-MT-ABC12345", content)


if __name__ == "__main__":
    unittest.main()
