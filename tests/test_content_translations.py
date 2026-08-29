import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.core.exceptions import ValidationException
from app.main import app
from app.modules.content_translations.models import ContentTranslation
from app.modules.content_translations.schemas import TranslationWrite
from app.modules.content_translations.service import localize_models, upsert, validate_entity_type, validate_fields, validate_locale
from app.modules.events.models import Event, EventStatus
from app.modules.store.models import Product
from app.modules.store.service import StoreService
from app.core.dependencies import require_admin
from fastapi import HTTPException
from app.modules.users.models import User


class ContentTranslationContractTests(unittest.TestCase):
    def test_admin_translation_routes_are_registered(self):
        paths = app.openapi()["paths"]
        base = "/api/v1/admin/content-translations/{entity_type}/{entity_id}"
        self.assertIn("get", paths[base])
        self.assertIn("put", paths[f"{base}/{{locale}}"])
        self.assertIn("delete", paths[f"{base}/{{locale}}"])

    def test_only_whitelisted_fields_can_be_translated(self):
        validate_fields("event", {"name": "论坛", "description": "说明"})
        with self.assertRaises(ValidationException) as context:
            validate_fields("event", {"status": "published"})
        self.assertEqual("INVALID_TRANSLATION_FIELD", context.exception.code)
        with self.assertRaises(ValidationException) as value_context:
            validate_fields("event", {"name": {"unsafe": "object"}})
        self.assertEqual("INVALID_TRANSLATION_VALUE", value_context.exception.code)

    def test_translation_rejects_blank_values(self):
        with self.assertRaises(ValueError):
            TranslationWrite(fields={"name": "  "})

    def test_entity_type_and_locale_are_validated_consistently(self):
        self.assertEqual("session", validate_entity_type("session"))
        self.assertEqual("zh-CN", validate_locale("zh-Hans"))
        with self.assertRaises(ValidationException) as entity_error:
            validate_entity_type("unknown")
        self.assertEqual("INVALID_TRANSLATION_ENTITY", entity_error.exception.code)
        with self.assertRaises(ValidationException) as locale_error:
            validate_locale("fr")
        self.assertEqual("UNSUPPORTED_LOCALE", locale_error.exception.code)

    def test_checkout_snapshot_keeps_localized_name_and_locale(self):
        product = Product(id=uuid4(), event_id=uuid4(), code="GOLD", name="Gold", product_type="delegate", price=100, currency="USD", metadata_json={"package_code": "GOLD"})
        translation = ContentTranslation(locale="zh-CN", fields={"name": "金牌套餐"})
        name, metadata = StoreService.localized_product_snapshot(product, translation)
        self.assertEqual("金牌套餐", name)
        self.assertEqual("zh-CN", metadata["content_locale"])
        self.assertEqual("GOLD", metadata["package_code"])


class ContentTranslationOverlayTests(unittest.IsolatedAsyncioTestCase):
    async def test_translation_admin_dependency_accepts_organizer_and_rejects_participant(self):
        organizer = User(id=uuid4(), email="organizer@example.com", password_hash="x", country="ID", role="organizer")
        participant = User(id=uuid4(), email="participant@example.com", password_hash="x", country="ID", role="participant")
        self.assertIs(organizer, await require_admin(organizer))
        with self.assertRaises(HTTPException) as context:
            await require_admin(participant)
        self.assertEqual(403, context.exception.status_code)

    async def test_upsert_creates_audited_translation(self):
        entity_id = uuid4()
        admin_id = uuid4()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db = AsyncMock()
        db.add = MagicMock()
        db.get.return_value = Event(id=entity_id, name="Forum")
        db.execute.return_value = result

        row = await upsert(db, "event", entity_id, "zh-CN", {"name": "商务论坛"}, admin_id)

        self.assertEqual("zh-CN", row.locale)
        self.assertEqual({"name": "商务论坛"}, row.fields)
        self.assertEqual(admin_id, row.created_by)
        db.add.assert_called_once_with(row)
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(row)

    async def test_translation_overlays_display_fields_without_changing_machine_fields(self):
        event_id = uuid4()
        event = Event(
            id=event_id,
            name="IWBIF Forum",
            slug="iwbif-forum",
            description="Forum description",
            timezone="Asia/Jakarta",
            start_at=datetime.now(timezone.utc),
            end_at=datetime.now(timezone.utc),
            capacity=100,
            status=EventStatus.PUBLISHED,
        )
        translation = ContentTranslation(
            id=uuid4(),
            entity_type="event",
            entity_id=event_id,
            locale="zh-CN",
            fields={"name": "IWBIF 商务论坛", "description": "论坛说明"},
        )
        result = MagicMock()
        result.scalars.return_value.all.return_value = [translation]
        db = AsyncMock()
        db.execute.return_value = result

        localized = (await localize_models(db, "event", [event], "zh-CN"))[0]

        self.assertEqual("IWBIF 商务论坛", localized["name"])
        self.assertEqual("论坛说明", localized["description"])
        self.assertEqual("published", localized["status"].value)
        self.assertEqual("iwbif-forum", localized["slug"])
        self.assertEqual("zh-CN", localized["content_locale"])
        self.assertFalse(localized["translation_fallback"])

    async def test_missing_chinese_translation_uses_source_and_marks_fallback(self):
        event = Event(
            id=uuid4(), name="Source", slug="source", timezone="Asia/Jakarta",
            start_at=datetime.now(timezone.utc), end_at=datetime.now(timezone.utc),
            capacity=10, status=EventStatus.PUBLISHED,
        )
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        db = AsyncMock()
        db.execute.return_value = result

        localized = (await localize_models(db, "event", [event], "zh-CN"))[0]
        self.assertEqual("Source", localized["name"])
        self.assertEqual("source", localized["content_locale"])
        self.assertTrue(localized["translation_fallback"])


if __name__ == "__main__":
    unittest.main()
