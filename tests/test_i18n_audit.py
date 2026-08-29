import unittest
from pathlib import Path

from scripts.audit_i18n_messages import scan_file, summary


class I18nMessageAuditTests(unittest.TestCase):
    def test_scanner_finds_success_messages_and_error_codes(self):
        findings = scan_file(Path("app/modules/content_translations/routes.py"))
        report = summary(findings)
        self.assertIn("Content translation updated", report["success_messages"])
        self.assertIn("CONTENT_TRANSLATION_NOT_FOUND", report["error_codes"])


if __name__ == "__main__":
    unittest.main()
