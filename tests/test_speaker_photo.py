import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import get_settings
from app.core.uploads import delete_uploaded_file
from app.main import app
from app.modules.speakers.routes import upload_speaker_photo
from app.modules.speakers.service import SpeakerService


class SpeakerPhotoContractTests(unittest.TestCase):
    def test_photo_endpoint_declares_speaker_id_as_uuid(self):
        operation = app.openapi()["paths"]["/api/v1/speakers/{speaker_id}/photo"]["post"]
        speaker_id = next(item for item in operation["parameters"] if item["name"] == "speaker_id")
        self.assertEqual("uuid", speaker_id["schema"]["format"])

    def test_delete_uploaded_file_rejects_path_outside_upload_root(self):
        settings = get_settings()
        original_dir = settings.UPLOAD_DIR
        with tempfile.TemporaryDirectory() as directory:
            settings.UPLOAD_DIR = directory
            outside = Path(directory).parent / "must-not-delete.jpg"
            outside.write_bytes(b"keep")
            try:
                self.assertFalse(delete_uploaded_file("/uploads/../must-not-delete.jpg"))
                self.assertTrue(outside.exists())
            finally:
                outside.unlink(missing_ok=True)
                settings.UPLOAD_DIR = original_dir


class SpeakerPhotoFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_replaces_photo_and_cleans_old_file(self):
        speaker_id = uuid.uuid4()
        request = SimpleNamespace(state=SimpleNamespace(request_id="request-id"))
        current = MagicMock(profile_photo_url="/uploads/speakers/old.jpg")
        updated = MagicMock()
        file = MagicMock()

        with (
            patch.object(SpeakerService, "get", AsyncMock(return_value=current)) as get_speaker,
            patch.object(SpeakerService, "update", AsyncMock(return_value=updated)) as update_speaker,
            patch("app.core.uploads.save_profile_photo", AsyncMock(return_value="/uploads/speakers/new.jpg")),
            patch("app.core.uploads.delete_uploaded_file", MagicMock()) as delete_file,
        ):
            response = await upload_speaker_photo(request, speaker_id, file, AsyncMock(), MagicMock())

        get_speaker.assert_awaited_once()
        update_speaker.assert_awaited_once()
        delete_file.assert_called_once_with("/uploads/speakers/old.jpg")
        self.assertTrue(response["success"])

    async def test_upload_cleans_new_file_when_database_update_fails(self):
        speaker_id = uuid.uuid4()
        request = SimpleNamespace(state=SimpleNamespace(request_id="request-id"))
        current = MagicMock(profile_photo_url=None)

        with (
            patch.object(SpeakerService, "get", AsyncMock(return_value=current)),
            patch.object(SpeakerService, "update", AsyncMock(side_effect=RuntimeError("db failed"))),
            patch("app.core.uploads.save_profile_photo", AsyncMock(return_value="/uploads/speakers/new.jpg")),
            patch("app.core.uploads.delete_uploaded_file", MagicMock()) as delete_file,
        ):
            with self.assertRaises(RuntimeError):
                await upload_speaker_photo(request, speaker_id, MagicMock(), AsyncMock(), MagicMock())

        delete_file.assert_called_once_with("/uploads/speakers/new.jpg")


if __name__ == "__main__":
    unittest.main()
