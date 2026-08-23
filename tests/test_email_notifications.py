import unittest

from app.modules.email_notifications.schemas import AccountPreferenceRead, AccountPreferenceWrite
from app.modules.email_notifications.service import DEFAULT_TEMPLATES, TRIGGER_VARIABLES, render
from uuid import uuid4


class EmailNotificationTemplateTests(unittest.TestCase):
    def test_every_trigger_has_default_and_declared_variables(self):
        self.assertEqual(set(DEFAULT_TEMPLATES), set(TRIGGER_VARIABLES))

    def test_render_replaces_known_variables_and_blanks_missing_values(self):
        rendered = render("Halo {{ participant_name }}, paket {{ package_name }} / {{ missing }}", {"participant_name": "Saptadi", "package_name": "Gold"})
        self.assertEqual("Halo Saptadi, paket Gold / ", rendered)

    def test_business_matching_and_commercial_triggers_are_available(self):
        expected = {
            "account_registered",
            "registration_submitted",
            "delegate_package_selected",
            "exhibitor_package_selected",
            "payment_confirmed",
            "business_matching_profile_saved",
            "meeting_requested",
            "meeting_accepted",
            "meeting_confirmed",
            "meeting_declined",
            "meeting_cancelled",
            "meeting_reschedule_requested",
        }
        self.assertEqual(expected, set(TRIGGER_VARIABLES))

    def test_account_preference_supports_override_and_restore_default(self):
        self.assertFalse(AccountPreferenceWrite(is_enabled=False).is_enabled)
        self.assertIsNone(AccountPreferenceWrite(is_enabled=None).is_enabled)

        preference = AccountPreferenceRead(
            event_id=uuid4(),
            user_id=uuid4(),
            trigger="payment_confirmed",
            global_enabled=True,
            override_enabled=False,
            effective_enabled=False,
        )
        self.assertFalse(preference.effective_enabled)
