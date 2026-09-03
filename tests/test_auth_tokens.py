import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from jose import jwt

from app.core.config import get_settings
from app.core.dependencies import decode_bearer_token
from app.core.security import _fallback_hash_password, verify_password


class BearerTokenTests(unittest.TestCase):
    @staticmethod
    def create_expired_token() -> str:
        settings = get_settings()
        return jwt.encode(
            {
                "sub": "test-user",
                "type": "access",
                "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

    def test_expired_token_returns_unauthorized(self):
        token = self.create_expired_token()

        with self.assertRaises(HTTPException) as caught:
            decode_bearer_token(token)

        self.assertEqual(401, caught.exception.status_code)
        self.assertEqual("Bearer token expired", caught.exception.detail)
        self.assertEqual("Bearer", caught.exception.headers["WWW-Authenticate"])

    def test_invalid_signature_returns_unauthorized(self):
        settings = get_settings()
        token = jwt.encode(
            {
                "sub": "test-user",
                "type": "access",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            },
            "incorrect-secret",
            algorithm=settings.JWT_ALGORITHM,
        )

        with self.assertRaises(HTTPException) as caught:
            decode_bearer_token(token)

        self.assertEqual(401, caught.exception.status_code)
        self.assertEqual("Invalid bearer token", caught.exception.detail)


class PasswordHashCompatibilityTests(unittest.TestCase):
    def test_fallback_hash_is_verified_even_when_passlib_is_available(self):
        hashed = _fallback_hash_password("Kupu!Dicky#2026-Temp")
        fake_context = MagicMock()
        with patch("app.core.security._pwd_context", fake_context):
            self.assertTrue(verify_password("Kupu!Dicky#2026-Temp", hashed))
            self.assertFalse(verify_password("incorrect", hashed))
        fake_context.verify.assert_not_called()

    def test_unknown_hash_returns_false_instead_of_raising(self):
        fake_context = MagicMock()
        fake_context.verify.side_effect = ValueError("unknown hash")
        with patch("app.core.security._pwd_context", fake_context):
            self.assertFalse(verify_password("password", "unknown-format"))


if __name__ == "__main__":
    unittest.main()
