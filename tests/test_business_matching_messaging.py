import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.main import app
from app.modules.business_matching.realtime import ConversationHub
from app.modules.business_matching.schemas import ConversationRead, MessageRead, NotificationRead
from app.modules.business_matching.models import MessageType
from app.modules.business_matching.routes import inbox_unread_count
from app.modules.business_matching.repository import BusinessMatchingRepository as Repo


class FakeWebSocket:
    def __init__(self):
        self.accepted = False
        self.events = []

    async def accept(self):
        self.accepted = True

    async def send_json(self, event):
        self.events.append(event)


class MessagingContractTests(unittest.TestCase):
    def test_openapi_contains_web_messaging_crud(self):
        paths = app.openapi()["paths"]
        self.assertIn("post", paths["/api/v1/conversations/{conversation_id}/messages"])
        self.assertIn("patch", paths["/api/v1/conversations/{conversation_id}/messages/{message_id}"])
        self.assertIn("delete", paths["/api/v1/conversations/{conversation_id}/messages/{message_id}"])
        self.assertIn("get", paths["/api/v1/messages/unread-count"])
        self.assertIn("get", paths["/api/v1/inbox/unread-count"])
        self.assertIn("get", paths["/api/v1/admin/notifications"])
        self.assertIn("get", paths["/api/v1/admin/notifications/unread-count"])
        self.assertIn("post", paths["/api/v1/admin/notifications/{notification_id}/read"])
        self.assertIn("post", paths["/api/v1/admin/notifications/read-all"])

    def test_conversation_contract_contains_counterpart_and_last_message(self):
        message = MessageRead(id=uuid.uuid4(), conversation_id=uuid.uuid4(), sender_participant_id=uuid.uuid4(), message_type=MessageType.TEXT, body="Hello", meeting_id=None, reply_to_message_id=None, created_at=datetime.now(timezone.utc))
        value = ConversationRead(id=message.conversation_id, event_id=uuid.uuid4(), status="active", other_participant_id=uuid.uuid4(), other_participant_name="Partner", unread_count=1, last_message=message)
        self.assertEqual(1, value.unread_count)
        self.assertEqual("Hello", value.last_message.body)

    def test_notification_contract_includes_payment_payload_fields(self):
        payload = NotificationRead(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            type="payment_status_update",
            title="Status pembayaran berubah",
            body="Pembayaran midtrans untuk order ORD-001 menjadi success",
            entity_type="order",
            entity_id=uuid.uuid4(),
            is_read=False,
            created_at=datetime.now(timezone.utc),
            read_at=None,
        )
        dumped = payload.model_dump()
        self.assertEqual("payment_status_update", dumped["type"])
        self.assertEqual("order", dumped["entity_type"])
        self.assertIn("user_id", dumped)


class MessagingRealtimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_hub_broadcasts_to_connected_clients(self):
        hub = ConversationHub()
        conversation_id = uuid.uuid4()
        socket = FakeWebSocket()
        await hub.connect(conversation_id, socket)
        await hub.broadcast(conversation_id, {"type": "new_message"})
        self.assertTrue(socket.accepted)
        self.assertEqual([{"type": "new_message"}], socket.events)
        await hub.disconnect(conversation_id, socket)


class InboxUnreadTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_without_participant_can_read_notification_badge(self):
        user = SimpleNamespace(id=uuid.uuid4(), role="organizer")
        request = SimpleNamespace(state=SimpleNamespace(request_id="test-request"))
        db = AsyncMock()

        with (
            patch.object(Repo, "participant_for_user", AsyncMock(return_value=None)),
            patch.object(Repo, "total_unread_messages", AsyncMock()) as message_count,
            patch.object(Repo, "unread_count", AsyncMock(return_value=4)),
        ):
            response = await inbox_unread_count(request=request, event_id=None, user=user, db=db)

        self.assertEqual(0, response["data"]["messages"])
        self.assertEqual(4, response["data"]["notifications"])
        self.assertEqual(4, response["data"]["unread_count"])
        message_count.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
