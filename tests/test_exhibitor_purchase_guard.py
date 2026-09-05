import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from pydantic import ValidationError
from app.core.exceptions import ConflictException
from app.modules.iwbif.schemas import ExhibitorRead, ExhibitorWrite
from app.modules.store.service import StoreService


class ExhibitorGuardTests(unittest.IsolatedAsyncioTestCase):
    def payload(self, booth):
        return dict(company_name="Company", brand="Brand", contact_person="Contact",
                    products_to_display="Products", booth_size_requested=booth,
                    electricity_requirement="220V", special_requirement="None",
                    exhibition_terms_accepted=True, exhibition_terms_version="v1")

    def test_booth_number_validation_and_legacy_read(self):
        for number in range(1, 41):
            self.assertEqual(str(number), ExhibitorWrite(**self.payload(str(number))).booth_size_requested)
        for invalid in ["0", "41", "1.5", "Premium Booth", ""]:
            with self.assertRaises(ValidationError):
                ExhibitorWrite(**self.payload(invalid))
        legacy = ExhibitorRead(**self.payload("Premium Booth"), email="test@example.com",
                              id=uuid4(), event_id=uuid4(), status="draft", created_at=datetime.now(timezone.utc))
        self.assertEqual("Premium Booth", legacy.booth_size_requested)

    async def test_availability_blocks_all_active_order_states_or_registration(self):
        for status, registered in [(s, False) for s in StoreService.ACTIVE_ORDER_STATUSES] + [(None, True), (None, False)]:
            with self.subTest(status=status, registered=registered):
                order = SimpleNamespace(id=uuid4(), status=status) if status else None
                order_result, registration_result = MagicMock(), MagicMock()
                order_result.scalars.return_value.first.return_value = order
                registration_result.scalar_one_or_none.return_value = uuid4() if registered else None
                db = AsyncMock()
                db.execute.side_effect = [order_result, registration_result]
                state = await StoreService.exhibitor_availability(db, uuid4(), uuid4())
                self.assertEqual(not (status or registered), state["is_purchasable"])
                self.assertEqual(order.id if order else None, state["existing_order_id"])
                query = str(db.execute.call_args_list[0].args[0])
                self.assertIn("orders.event_id", query)
                self.assertIn("orders.user_id", query)
                self.assertIn("orders.status IN", query)

    async def test_existing_purchase_rejected_at_add_and_checkout(self):
        event_id, user_id = uuid4(), uuid4()
        product = SimpleNamespace(id=uuid4(), event_id=event_id, is_active=True, product_type="exhibitor")
        for operation in ["add", "checkout"]:
            with self.subTest(operation=operation):
                db = AsyncMock()
                db.get.return_value = product
                cart_result, rows_result = MagicMock(), MagicMock()
                cart_result.scalar_one_or_none.return_value = SimpleNamespace(id=uuid4())
                rows_result.all.return_value = [(SimpleNamespace(quantity=1), product)]
                db.execute.side_effect = [MagicMock(), cart_result, rows_result, MagicMock()] if operation == "checkout" else None
                with patch.object(StoreService, "exhibitor_availability", AsyncMock(return_value={"is_purchasable": False})):
                    with self.assertRaises(ConflictException) as caught:
                        if operation == "add":
                            await StoreService.add_item(db, user_id, event_id, SimpleNamespace(product_id=product.id, quantity=1))
                        else:
                            await StoreService.checkout(db, user_id, event_id)
                self.assertEqual("EXHIBITOR_PACKAGE_ALREADY_SELECTED", caught.exception.code)
                db.commit.assert_not_awaited()
