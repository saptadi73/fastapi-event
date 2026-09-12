import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.modules.iwbif.models import DelegateRegistrationDetail
from app.modules.iwbif.schemas import DelegateRegistrationWrite
from app.modules.iwbif.service import IwbifService


class DelegateIdentityTests(unittest.IsolatedAsyncioTestCase):
    def test_documented_payload_and_legacy_identity(self):
        document = (Path(__file__).parents[1] / "docs/API_REFERENCE.md").read_text(encoding="utf-8")
        block = next(block for block in re.findall(r"```json\n(.*?)\n```", document, re.S) if '"business_objectives":"Find partners"' in block)
        payload = json.loads(block.replace('"uuid"', f'"{uuid4()}"'))
        clean = DelegateRegistrationWrite(**payload).model_dump()
        fields = {"full_name", "title", "nationality", "email"}
        legacy = DelegateRegistrationWrite(**payload, **dict.fromkeys(fields, "ignored")).model_dump()
        self.assertEqual(clean, legacy)
        self.assertTrue(fields.isdisjoint(DelegateRegistrationWrite.model_json_schema()["properties"]))

    def test_response_hides_legacy_identity(self):
        detail = DelegateRegistrationDetail(full_name="Old name", email="old@example.com", title="Ms", nationality="Indonesian", job_title="Director")
        reg = SimpleNamespace(id=uuid4(), event_id=uuid4(), participant_id=uuid4(), registration_number="TEST", status="draft")
        result = IwbifService.serialize_registration(reg, detail)["detail"]
        self.assertEqual(result["job_title"], "Director")
        self.assertTrue({"full_name", "title", "nationality", "email"}.isdisjoint(result))

    async def test_participant_without_account_name_uses_email(self):
        db = AsyncMock()
        db.add = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result
        db.get.return_value = SimpleNamespace(id=uuid4(), full_name=None, email="account@example.com")
        participant = await IwbifService.resolve_participant(db, db.get.return_value.id)
        self.assertEqual(participant.full_name, "account@example.com")
