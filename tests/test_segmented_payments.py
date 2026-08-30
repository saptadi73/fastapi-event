import unittest
from decimal import Decimal

from app.core.config import get_settings
from app.modules.payments.models import OrderStatus, order_allowed_actions
from app.modules.payments.service import PaymentService


class SegmentedPaymentPlanTests(unittest.TestCase):
    def setUp(self):
        self.settings = get_settings()
        self.original_rate = self.settings.PAYMENT_USD_TO_IDR_RATE
        self.original_limit = self.settings.QRIS_SEGMENT_LIMIT_IDR
        self.settings.PAYMENT_USD_TO_IDR_RATE = 18_000
        self.settings.QRIS_SEGMENT_LIMIT_IDR = 9_000_000

    def tearDown(self):
        self.settings.PAYMENT_USD_TO_IDR_RATE = self.original_rate
        self.settings.QRIS_SEGMENT_LIMIT_IDR = self.original_limit

    def test_usd_500_is_single_idr_9m_segment(self):
        self.assertEqual([Decimal("9000000.00")], PaymentService._segment_plan(Decimal("9000000")))

    def test_above_usd_500_is_split_deterministically(self):
        self.assertEqual(
            [Decimal("9000000"), Decimal("900000.00")],
            PaymentService._segment_plan(Decimal("9900000")),
        )

    def test_large_order_uses_as_many_segments_as_required(self):
        self.assertEqual(
            [Decimal("9000000"), Decimal("9000000"), Decimal("9000000.00")],
            PaymentService._segment_plan(Decimal("27000000")),
        )

    def test_partially_paid_order_can_continue_but_is_not_paid(self):
        self.assertIn("continue_payment", order_allowed_actions(OrderStatus.PARTIALLY_PAID))
        self.assertNotEqual(OrderStatus.PAID, OrderStatus.PARTIALLY_PAID)


if __name__ == "__main__":
    unittest.main()
