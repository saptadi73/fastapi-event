import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import FastAPI

from app.core.dependencies import get_current_user, get_db_session
from app.middleware.error_handler import add_exception_handlers
from app.modules.identity.routes import router


class UserDetailValidationTests(unittest.IsolatedAsyncioTestCase):
    async def request_detail(self, user_id, current_user):
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        add_exception_handlers(app)
        app.dependency_overrides[get_current_user] = lambda: current_user
        app.dependency_overrides[get_db_session] = lambda: None
        messages = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        path = f"/api/v1/auth/users/{user_id}"
        await app({
            "type": "http", "asgi": {"version": "3.0"},
            "http_version": "1.1", "method": "GET", "scheme": "http",
            "path": path, "raw_path": path.encode(),
            "query_string": b"locale=en", "headers": [],
            "client": ("127.0.0.1", 12345), "server": ("testserver", 80),
            "root_path": "",
        }, receive, send)
        status = next(m["status"] for m in messages if m["type"] == "http.response.start")
        body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
        return status, json.loads(body)

    async def test_placeholder_id_rejected_before_service_query(self):
        with patch("app.modules.identity.routes.UserService.get_registration_detail", new_callable=AsyncMock) as detail:
            status, body = await self.request_detail(
                "organizer-test", SimpleNamespace(id=uuid4(), role="organizer"),
            )
        self.assertEqual(422, status)
        self.assertFalse(body["success"])
        self.assertEqual("path.user_id", body["errors"][0]["field"])
        detail.assert_not_awaited()

    async def test_owner_uuid_is_accepted_and_passed_as_uuid(self):
        user_id = uuid4()
        with patch("app.modules.identity.routes.UserService.get_registration_detail", new_callable=AsyncMock, return_value={}) as detail:
            status, body = await self.request_detail(
                str(user_id), SimpleNamespace(id=user_id, role="participant"),
            )
        self.assertEqual(200, status)
        self.assertTrue(body["success"])
        detail.assert_awaited_once_with(None, user_id)

    async def test_other_participant_remains_forbidden(self):
        with patch("app.modules.identity.routes.UserService.get_registration_detail", new_callable=AsyncMock) as detail:
            status, _ = await self.request_detail(
                str(uuid4()), SimpleNamespace(id=uuid4(), role="participant"),
            )
        self.assertEqual(403, status)
        detail.assert_not_awaited()

    async def test_organizer_can_read_another_user(self):
        with patch("app.modules.identity.routes.UserService.get_registration_detail", new_callable=AsyncMock, return_value={}):
            status, _ = await self.request_detail(
                str(uuid4()), SimpleNamespace(id=uuid4(), role="organizer"),
            )
        self.assertEqual(200, status)
