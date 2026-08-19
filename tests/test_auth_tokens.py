import unittest
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from jose import jwt

from app.core.config import get_settings
from app.core.dependencies import decode_bearer_token


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


if __name__ == "__main__":
    unittest.main()