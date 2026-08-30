import unittest
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import ConflictException
from app.modules.iwbif.models import DelegatePackage, DelegatePackageRate, DelegateRegistrationPackageSelection
from app.modules.payments.models import Order, OrderKind, OrderStatus
from app.modules.payments.service import PaymentService
from app.modules.registrations.models import RegistrationStatus
from app.modules.store.models import OrderItem, Product
from app.modules.store.service import StoreService


class AdditionalPackageOrderTests(unittest.IsolatedAsyncioTestCase):
    async def test_owned_additional_cannot_be_added_to_cart_again(self):
        event_id, user_id, package_id, rate_id, product_id = [uuid.uuid4() for _ in range(5)]
        product = Product(id=product_id, event_id=event_id, delegate_package_rate_id=rate_id, code="ADD", name="Add", product_type="additional", price=100, currency="IDR", max_quantity=1, is_active=True)
        rate = DelegatePackageRate(id=rate_id, delegate_package_id=package_id, occupancy_type="default", name="Default", amount=100, currency="USD", is_active=True, is_default=True)
        package = DelegatePackage(id=package_id, event_id=event_id, code="ADD", name="Add", package_type="additional", selection_mode="optional", amount=100, currency="USD", is_active=True, display_order=1)
        db = AsyncMock()

        async def get(model, identifier):
            return {Product: product, DelegatePackageRate: rate, DelegatePackage: package}.get(model)

        db.get.side_effect = get
        cart = SimpleNamespace(id=uuid.uuid4())
        payload = SimpleNamespace(product_id=product_id, quantity=1)
        with patch.object(StoreService, "get_cart", AsyncMock(return_value=(cart, []))), patch.object(StoreService, "_additional_purchase_state", AsyncMock(return_value=("owned", None, SimpleNamespace(id=uuid.uuid4())))):
            with self.assertRaises(ConflictException) as caught:
                await StoreService.add_item(db, user_id, event_id, payload)
        self.assertEqual("ADDITIONAL_PACKAGE_NOT_AVAILABLE", caught.exception.code)

    async def test_paid_additional_is_attached_to_registration_idempotently(self):
        registration_id, order_id, package_id, rate_id, item_id = [uuid.uuid4() for _ in range(5)]
        order = Order(id=order_id, registration_id=registration_id, order_kind=OrderKind.ADDITIONAL, status=OrderStatus.PAID, total_amount=100, currency="IDR")
        package = DelegatePackage(id=package_id, code="TRIP", name="Trip", package_type="additional", amount=10, currency="USD")
        rate = DelegatePackageRate(id=rate_id, delegate_package_id=package_id, occupancy_type="default", name="Default", amount=10, currency="USD")
        item = OrderItem(id=item_id, order_id=order_id, product_code="TRIP", product_name="Trip", product_type="additional", quantity=1, unit_price=100, line_total=100, currency="IDR", metadata_json={})
        rows_result = MagicMock()
        rows_result.all.return_value = [(package, rate, item)]
        missing_result = MagicMock()
        missing_result.scalar_one_or_none.return_value = None
        db = AsyncMock()
        db.execute.side_effect = [rows_result, missing_result]
        db.add = MagicMock()

        await PaymentService._activate_paid_additional_packages(db, order)

        selection = db.add.call_args.args[0]
        self.assertIsInstance(selection, DelegateRegistrationPackageSelection)
        self.assertEqual(registration_id, selection.registration_id)
        self.assertEqual(package_id, selection.delegate_package_id)
        self.assertEqual(order_id, selection.source_order_id)

    async def test_partial_additional_does_not_downgrade_main_registration(self):
        order = Order(id=uuid.uuid4(), registration_id=uuid.uuid4(), order_kind=OrderKind.ADDITIONAL, status=OrderStatus.PENDING, total_amount=200, currency="IDR")
        db = AsyncMock()
        with patch.object(PaymentService, "_payment_progress", AsyncMock(return_value=(Decimal("100"), Decimal("100")))):
            paid, remaining, became_paid = await PaymentService._reconcile_order_payment(db, order)
        self.assertEqual(OrderStatus.PARTIALLY_PAID, order.status)
        self.assertEqual(Decimal("100"), paid)
        self.assertFalse(became_paid)
        db.get.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
