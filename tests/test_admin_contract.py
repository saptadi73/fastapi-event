import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from app.main import app
from app.modules.users.schemas import UserRead
from app.modules.identity import routes as identity_routes
from app.modules.users.schemas import UserLogin


class AdminApiContractTests(unittest.TestCase):
    def test_user_read_exposes_role(self):
        user = SimpleNamespace(
            id=uuid4(),
            email="organizer@iwbif2026.org",
            full_name="Organizer",
            phone="+6281100002026",
            country="Indonesia",
            status="active",
            registration_status="account_created",
            role="organizer",
            is_email_verified=True,
            created_at=datetime.now(timezone.utc),
        )
        self.assertEqual("organizer", UserRead.model_validate(user).role)

    def test_admin_content_routes_are_registered(self):
        routes = {
            (method.upper(), path)
            for path, operations in app.openapi()["paths"].items()
            for method in operations
        }
        expected = {
            ("DELETE", "/api/v1/speakers/{speaker_id}"),
            ("POST", "/api/v1/speakers/{speaker_id}/events"),
            ("DELETE", "/api/v1/speakers/{speaker_id}/events/{event_id}"),
            ("DELETE", "/api/v1/sessions/{session_id}"),
            ("DELETE", "/api/v1/events/{event_id}"),
            ("DELETE", "/api/v1/store/admin/products/{product_id}"),
            ("PUT", "/api/v1/auth/password"),
            ("POST", "/api/v1/admin/events/{event_id}/announcements"),
            ("DELETE", "/api/v1/admin/announcements/{item_id}"),
            ("GET", "/api/v1/certificates/me"),
            ("POST", "/api/v1/admin/certificates"),
            ("DELETE", "/api/v1/admin/certificates/{item_id}"),
        }
        self.assertTrue(expected.issubset(routes), expected - routes)


class LoginContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_returns_role_and_complete_tracking_snapshot(self):
        user_id = uuid4()
        user = SimpleNamespace(id=user_id)
        tracking = {
            "user": {"id": str(user_id), "role": "organizer"},
            "registration_status": "paid",
            "delegate_status": "lengkap",
            "exhibitor_status": "belum_terdaftar",
            "purchase_tracking": {"delegate": {}, "exhibitor": {}},
            "selected_types": ["delegate"],
            "profile": None,
            "registrations": [],
            "orders": [],
        }
        request = SimpleNamespace(state=SimpleNamespace(request_id="test"))
        with patch.object(identity_routes.UserService, "login", AsyncMock(return_value=(user, "access", "refresh"))), patch.object(
            identity_routes.UserService, "get_registration_detail", AsyncMock(return_value=tracking)
        ) as get_detail:
            response = await identity_routes.login(
                request=request,
                payload=UserLogin(email="organizer@iwbif2026.org", password="password123"),
                db=object(),
            )
        self.assertEqual("organizer", response["data"]["user"]["role"])
        self.assertEqual("paid", response["data"]["registration_status"])
        self.assertIn("delegate", response["data"]["purchase_tracking"])
        self.assertIn("exhibitor", response["data"]["purchase_tracking"])
        get_detail.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
