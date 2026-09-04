import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.modules.iwbif.models import ExhibitorRegistration
from app.modules.iwbif.routes import update_exhibitor
from app.modules.iwbif.schemas import ExhibitorWrite
from app.modules.iwbif.service import IwbifService


def exhibitor_payload(**extra):
    return ExhibitorWrite(
        company_name="Example SME", brand="Example Brand",
        contact_person="Contact Name", products_to_display="Food products",
        booth_size_requested="Standard Booth 3x3",
        electricity_requirement="220V", special_requirement="None",
        exhibition_terms_accepted=True, exhibition_terms_version="v1", **extra,
    )


class ExhibitorEmailTests(unittest.IsolatedAsyncioTestCase):
    def test_email_is_not_an_input_field(self):
        self.assertNotIn("email", ExhibitorWrite.model_json_schema()["properties"])
        self.assertNotIn("email", exhibitor_payload().model_dump())

    async def test_create_uses_account_email_without_email_input(self):
        event_id, user_id = uuid4(), uuid4()
        user = SimpleNamespace(email="account@example.com", country="Indonesia")
        participant = SimpleNamespace(id=uuid4())
        database = AsyncMock()
        database.add = MagicMock()
        database.get.side_effect = [SimpleNamespace(id=event_id), user, user]
        result = MagicMock()
        result.first.return_value = None
        database.execute.return_value = result
        with (
            patch.object(IwbifService, "require_purchased_exhibitor_package", AsyncMock()),
            patch.object(IwbifService, "resolve_participant", AsyncMock(return_value=participant)),
            patch.object(IwbifService, "upsert_company", AsyncMock(return_value=SimpleNamespace(id=uuid4()))),
        ):
            row = await IwbifService.create_exhibitor(database, event_id, user_id, exhibitor_payload())
        self.assertEqual(user.email, row.email)
        database.commit.assert_awaited_once()

    async def test_update_ignores_legacy_email_input_and_uses_account(self):
        event_id, user_id, participant_id = uuid4(), uuid4(), uuid4()
        user = SimpleNamespace(id=user_id, email="account@example.com", country="Indonesia")
        row = ExhibitorRegistration(
            **exhibitor_payload().model_dump(exclude={"participant_id"}),
            id=uuid4(), event_id=event_id, participant_id=participant_id,
            email="old@example.com", status="draft", created_at=datetime.now(timezone.utc),
        )
        database = AsyncMock()
        database.get.side_effect = [row, SimpleNamespace(user_id=user_id), user]
        with (
            patch.object(IwbifService, "upsert_company", AsyncMock(return_value=SimpleNamespace(id=uuid4()))),
            patch("app.modules.iwbif.routes.success_response") as response,
        ):
            await update_exhibitor(
                event_id, row.id, exhibitor_payload(email="override@example.com"),
                request=MagicMock(), user=user, db=database,
            )
        self.assertEqual(user.email, row.email)
        self.assertEqual(user.email, response.call_args.args[1].email)
        database.commit.assert_awaited_once()
