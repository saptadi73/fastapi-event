import unittest
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.modules.iwbif.service import IwbifService
from app.modules.payments.models import Order
from app.modules.payments.schemas import CreateDokuCheckoutRequest, OrderRead
from app.modules.registrations.models import Registration, RegistrationStatus
from app.modules.store.service import StoreService


class PaymentContractTests(unittest.TestCase):
    def test_checkout_requires_exactly_one_payment_source(self):
        order_id = uuid.uuid4()
        registration_id = uuid.uuid4()

        self.assertEqual(order_id, CreateDokuCheckoutRequest(order_id=order_id).order_id)
        self.assertEqual(
            registration_id,
            CreateDokuCheckoutRequest(registration_id=registration_id).registration_id,
        )
        with self.assertRaises(ValidationError):
            CreateDokuCheckoutRequest()
        with self.assertRaises(ValidationError):
            CreateDokuCheckoutRequest(order_id=order_id, registration_id=registration_id)

    def test_pre_registration_order_serializes_with_null_registration(self):
        order = Order(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            registration_id=None,
            order_number="ORD-TEST",
            subtotal=Decimal("10000"),
            discount_amount=Decimal("0"),
            tax_amount=Decimal("0"),
            service_fee=Decimal("0"),
            total_amount=Decimal("10000"),
            currency="IDR",
            status="pending",
        )

        self.assertIsNone(OrderRead.model_validate(order).registration_id)


class RegistrationLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_submit_rejects_wrong_event_before_database_mutation(self):
        database = AsyncMock()
        registration = SimpleNamespace(event_id=uuid.uuid4())

        with patch.object(
            IwbifService,
            "owned_registration",
            AsyncMock(return_value=registration),
        ):
            with self.assertRaises(NotFoundException):
                await IwbifService.submit(
                    database,
                    uuid.uuid4(),
                    uuid.uuid4(),
                    uuid.uuid4(),
                )

        database.execute.assert_not_awaited()
        database.commit.assert_not_awaited()

    async def test_confirmation_requires_paid_linked_order(self):
        database = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        database.execute.return_value = result

        with self.assertRaises(ConflictException):
            await IwbifService.require_paid_order(database, uuid.uuid4())

        result.scalar_one_or_none.return_value = uuid.uuid4()
        await IwbifService.require_paid_order(database, uuid.uuid4())

    async def test_checkout_locks_cart_before_reading_items(self):
        database = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        database.execute.return_value = result

        with self.assertRaises(ValidationException):
            await StoreService.checkout(database, uuid.uuid4(), uuid.uuid4())

        statement = database.execute.await_args.args[0]
        self.assertIsNotNone(statement._for_update_arg)


class RegistrationModelTests(unittest.TestCase):
    def test_registration_status_persists_lowercase_values(self):
        status_type = Registration.__table__.c.status.type
        processor = status_type.bind_processor(postgresql.dialect())

        self.assertEqual("draft", processor(RegistrationStatus.DRAFT))
        self.assertEqual("cancelled", processor(RegistrationStatus.CANCELLED))


if __name__ == "__main__":
    unittest.main()