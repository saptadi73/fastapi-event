import unittest
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.modules.payments.models import Order, OrderStatus
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.service import PaymentService
from app.modules.store.models import OrderItem


class PendingOrderNameTests(unittest.IsolatedAsyncioTestCase):
    async def detail(self, status="pending", metadata=True, catalog=True, product_link=True):
        product_id, rate_id = uuid.uuid4(), uuid.uuid4()
        order = Order(id=uuid.uuid4(), user_id=uuid.uuid4(), event_id=uuid.uuid4(), registration_id=None,
                      order_number="ORD-NAME", order_kind="main_registration", subtotal=12600000,
                      discount_amount=0, tax_amount=0, service_fee=0, total_amount=12600000,
                      currency="IDR", status=status)
        item = OrderItem(id=uuid.uuid4(), order_id=order.id, product_id=product_id,
                         product_code="DELEGATE_A_SHARING", product_name="Package A - USD500 - Twin Sharing Basis",
                         product_type="delegate", quantity=1, unit_price=9000000, line_total=9000000,
                         currency="IDR", metadata_json={"delegate_package_rate_id": str(rate_id)} if metadata else {})
        result = MagicMock()
        result.scalars.return_value.all.return_value = [item]
        results = [result]
        if "continue_payment" in order.allowed_actions:
            products = MagicMock()
            products.all.return_value = [(product_id, "Package A - USD500 - Twin Sharing Basis",
                                          "Package A (5-star Hotel)" if catalog and product_link else None,
                                          "Twin Sharing Basis" if catalog and product_link else None)]
            results.append(products)
            if metadata:
                rates = MagicMock()
                rates.all.return_value = [(rate_id, "Package A (5-star Hotel)", "Twin Sharing Basis")] if catalog else []
                results.append(rates)
        session = AsyncMock()
        session.execute.side_effect = results
        paid = Decimal("12600000") if status == OrderStatus.PAID else Decimal("0")
        with patch.object(PaymentRepository, "get_payments_by_order", AsyncMock(return_value=[])), patch.object(PaymentService, "_payment_progress", AsyncMock(return_value=(paid, Decimal("12600000") - paid))):
            detail = await PaymentService._user_order_detail(session, order)
        self.assertEqual(9000000, detail.items[0].unit_price)
        self.assertEqual(12600000, detail.order.total_amount)
        self.assertEqual("Package A - USD500 - Twin Sharing Basis", item.product_name)
        session.commit.assert_not_awaited()
        return detail

    async def test_live_rate_name_wins_over_stale_product_name(self):
        detail = await self.detail(product_link=False)
        self.assertEqual("Package A (5-star Hotel) - Twin Sharing Basis", detail.items[0].product_name)

    async def test_product_rate_link_resolves_name_without_order_metadata(self):
        detail = await self.detail(metadata=False)
        self.assertEqual("Package A (5-star Hotel) - Twin Sharing Basis", detail.items[0].product_name)

    async def test_partial_and_expired_resumable_orders_use_current_name(self):
        for status in ["partially_paid", "expired"]:
            with self.subTest(status=status):
                detail = await self.detail(status=status)
                self.assertEqual("Package A (5-star Hotel) - Twin Sharing Basis", detail.items[0].product_name)

    async def test_paid_invoice_preserves_purchase_name(self):
        detail = await self.detail(status="paid")
        self.assertEqual("Package A - USD500 - Twin Sharing Basis", detail.items[0].product_name)

    async def test_removed_catalog_entry_falls_back_to_product_name(self):
        detail = await self.detail(catalog=False)
        self.assertEqual("Package A - USD500 - Twin Sharing Basis", detail.items[0].product_name)
