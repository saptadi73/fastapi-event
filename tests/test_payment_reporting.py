import unittest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.dialects import postgresql

from app.modules.payments.reporting import PaymentReportingService
from app.modules.payments.schemas import TransactionStatusUpdateRequest


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
    def test_organizer_status_contract_accepts_paid_success_and_cancelled(self):
        for status in ("paid", "success", "cancelled"):
            self.assertEqual(status, TransactionStatusUpdateRequest(status=status).status)

    def test_cancelled_transaction_is_not_counted_as_revenue(self):
        report = PaymentReportingService.build_report(
            [payment_row("cancelled", "10000.00", "MIDTRANS")], limit=10, offset=0
        )
        self.assertEqual(0, report["summary"]["successful_transactions"])
        self.assertEqual(0, report["summary"]["gross_revenue"])

    def test_store_first_payment_without_registration_still_counts(self):
        row = payment_row("success", "10000.00", "MIDTRANS")
        for key in (
            "registration_id", "registration_number", "event_id", "event_name",
            "customer_name", "customer_email", "package_id", "package_code", "package_name",
        ):
            row[key] = None

        report = PaymentReportingService.build_report([row], limit=10, offset=0)

        self.assertEqual(report["summary"]["total_transactions"], 1)
        self.assertEqual(report["summary"]["successful_transactions"], 1)
        self.assertEqual(report["summary"]["gross_revenue"], 10000.0)
        self.assertEqual(report["by_package"][0]["package_name"], "Unassigned")

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

    def test_report_serializes_payment_proof_download_link(self):
        row = payment_row("pending", "10000.00", "MANUAL_TRANSFER")
        proof_id = uuid.uuid4()
        row["provider"] = "manual_transfer"
        row["payment_proof_count"] = 1
        row["payment_proofs"] = [{
            "id": proof_id,
            "original_filename": "receipt.jpg",
            "mime_type": "image/jpeg",
            "file_size": 1200,
            "notes": None,
            "uploaded_by": uuid.uuid4(),
            "created_at": row["created_at"],
            "download_url": f"/api/v1/payments/manual-proofs/{proof_id}/download",
        }]

        transaction = PaymentReportingService.build_report([row], limit=10, offset=0)["transactions"][0]

        self.assertEqual(transaction["payment_proof_count"], 1)
        self.assertEqual(transaction["payment_proofs"][0]["id"], str(proof_id))
        self.assertIn(str(proof_id), transaction["payment_proofs"][0]["download_url"])


class PaymentReportingQueryTests(unittest.IsolatedAsyncioTestCase):
    async def test_store_order_context_supports_event_and_package_filters(self):
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        session.execute.return_value = result

        await PaymentReportingService.rows(
            session,
            provider="midtrans",
            event_id=uuid.uuid4(),
            package_id=uuid.uuid4(),
        )

        statement = session.execute.await_args.args[0]
        sql = str(statement.compile(dialect=postgresql.dialect()))
        self.assertIn("coalesce", sql.lower())
        self.assertIn("order_items", sql)
        self.assertIn("products", sql)


if __name__ == "__main__":
    unittest.main()
