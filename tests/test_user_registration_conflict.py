import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.core.exceptions import ConflictException
from app.modules.users.repository import UserRepository


class UserRegistrationConflictTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_email_returns_explicit_email_conflict(self):
        result = SimpleNamespace(scalar_one_or_none=lambda: object())
        session = SimpleNamespace(execute=AsyncMock(return_value=result))

        with self.assertRaises(ConflictException) as caught:
            await UserRepository.create(
                session,
                email="registered@example.com",
                password_hash="hashed-password",
                country="Indonesia",
                phone="+6285813826719",
            )

        self.assertEqual("USER_EXISTS", caught.exception.code)
        self.assertEqual("Email sudah terdaftar", caught.exception.message)
        self.assertEqual("email", caught.exception.field)


if __name__ == "__main__":
    unittest.main()
