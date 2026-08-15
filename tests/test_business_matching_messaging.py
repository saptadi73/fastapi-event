import unittest
import uuid
from datetime import datetime, timezone

from app.main import app
from app.modules.business_matching.realtime import ConversationHub
from app.modules.business_matching.schemas import ConversationRead, MessageRead
from app.modules.business_matching.models import MessageType


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

    def test_conversation_contract_contains_counterpart_and_last_message(self):
        message = MessageRead(id=uuid.uuid4(), conversation_id=uuid.uuid4(), sender_participant_id=uuid.uuid4(), message_type=MessageType.TEXT, body="Hello", meeting_id=None, reply_to_message_id=None, created_at=datetime.now(timezone.utc))
        value = ConversationRead(id=message.conversation_id, event_id=uuid.uuid4(), status="active", other_participant_id=uuid.uuid4(), other_participant_name="Partner", unread_count=1, last_message=message)
        self.assertEqual(1, value.unread_count)
        self.assertEqual("Hello", value.last_message.body)


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


if __name__ == "__main__":
    unittest.main()
