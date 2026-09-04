import unittest

from app.main import app
from app.modules.committee.schemas import CommitteeMemberCreate
from app.modules.content_translations.service import TRANSLATABLE_FIELDS, _model_for


class CommitteeContractTests(unittest.TestCase):
    def test_committee_routes_are_registered(self):
        paths = app.openapi()["paths"]
        self.assertIn("get", paths["/api/v1/events/{event_id}/committee"])
        self.assertIn("get", paths["/api/v1/admin/committee"])
        self.assertIn("post", paths["/api/v1/admin/committee"])
        self.assertIn("put", paths["/api/v1/admin/committee/{member_id}"])
        self.assertIn("delete", paths["/api/v1/admin/committee/{member_id}"])
        self.assertIn("post", paths["/api/v1/admin/committee/{member_id}/photo"])

    def test_committee_chinese_translation_fields_are_supported(self):
        self.assertEqual(
            {"role_title", "committee_group", "organization_name", "biography"},
            set(TRANSLATABLE_FIELDS["committee_member"]),
        )
        self.assertEqual("committee_members", _model_for("committee_member").__tablename__)

    def test_create_schema_defaults_to_draft(self):
        payload = CommitteeMemberCreate(
            event_id="851b8005-6aa5-4468-8525-4e7e56329195",
            full_name="Committee Member",
            role_title="Committee Chair",
        )
        self.assertEqual("draft", payload.status)
        self.assertEqual(0, payload.display_order)


if __name__ == "__main__":
    unittest.main()
