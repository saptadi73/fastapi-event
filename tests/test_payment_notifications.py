import unittest
import uuid
from unittest.mock import AsyncMock, patch

from app.modules.payments.models import Order, Payment
from app.modules.payments.service import PaymentService
from app.modules.registrations.models import Registration


class PaymentNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_notify_payment_status_notifies_owner_and_admin(self):
        owner_user_id = uuid.uuid4()
        admin_user_id = uuid.uuid4()
        event_id = uuid.uuid4()
        registration_id = uuid.uuid4()
        order_id = uuid.uuid4()
        order = Order(id=order_id, registration_id=registration_id, user_id=owner_user_id, status="pending")
        payment = Payment(id=uuid.uuid4(), order_id=order_id, provider="midtrans", transaction_status="pending")
        registration = Registration(id=registration_id, event_id=event_id, participant_id=uuid.uuid4(), status="awaiting_payment")

        session = AsyncMock()
        session.get = AsyncMock(return_value=registration)

        with patch.object(PaymentService, "_admin_user_ids", AsyncMock(return_value=[admin_user_id])):
            await PaymentService._notify_payment_status(session, order, payment)

        added = [call.args[0] for call in session.add.call_args_list]
        self.assertEqual(2, len(added))
        recipients = [row.user_id for row in added]
        self.assertIn(owner_user_id, recipients)
        self.assertIn(admin_user_id, recipients)
        self.assertTrue(all(row.event_id == event_id for row in added))

    async def test_notify_payment_status_skips_actor_when_actor_is_owner(self):
        owner_user_id = uuid.uuid4()
        admin_user_id = uuid.uuid4()
        event_id = uuid.uuid4()
        registration_id = uuid.uuid4()
        order_id = uuid.uuid4()
        order = Order(id=order_id, registration_id=registration_id, user_id=owner_user_id, status="pending")
        payment = Payment(id=uuid.uuid4(), order_id=order_id, provider="midtrans", transaction_status="pending")
        registration = Registration(id=registration_id, event_id=event_id, participant_id=uuid.uuid4(), status="awaiting_payment")

        session = AsyncMock()
        session.get = AsyncMock(return_value=registration)

        with patch.object(PaymentService, "_admin_user_ids", AsyncMock(return_value=[admin_user_id, owner_user_id])):
            await PaymentService._notify_payment_status(session, order, payment, actor_user_id=owner_user_id)

        recipients = [call.args[0].user_id for call in session.add.call_args_list]
        self.assertEqual([admin_user_id], recipients)


if __name__ == "__main__":
    unittest.main()
