import sqlite3
import unittest
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.dialects import sqlite

from app.core.database import Base
from app.modules.payments.reporting import PaymentReportingService


class TransactionIdentityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        session.execute.return_value = result
        await PaymentReportingService.rows(session, provider=None)
        statement = session.execute.await_args.args[0]
        self.sql = str(statement.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        # Execute the real report SELECT against isolated identity/payment fixtures.
        # Other model columns are nullable here so unrelated domain setup is unnecessary.
        for table in Base.metadata.tables.values():
            columns = ", ".join(f'"{column.name}"' for column in table.columns)
            self.db.execute(f'CREATE TABLE "{table.name}" ({columns})')

    async def asyncTearDown(self):
        self.db.close()

    def insert(self, table, **values):
        columns = ", ".join(f'"{name}"' for name in values)
        placeholders = ", ".join("?" for _ in values)
        self.db.execute(f'INSERT INTO "{table}" ({columns}) VALUES ({placeholders})', tuple(values.values()))

    def order(self, registration_id=None):
        self.insert("orders", id="order", user_id="owner", registration_id=registration_id, order_number="ORD-TEST", status="pending")
        for payment_id in ("payment-1", "payment-2"):
            self.insert("payments", id=payment_id, order_id="order", provider="midtrans", transaction_status="pending", gross_amount=100, currency="IDR", created_at="2026-09-07")

    def registration(self, profile_name="Registered participant", user_name="Account participant"):
        self.insert("users", id="registered-user", full_name=user_name, email="registered@example.com")
        self.insert("participants", id="participant", user_id="registered-user", full_name=profile_name)
        self.insert("registrations", id="registration", participant_id="participant", registration_number="REG-TEST")
        self.order("registration")

    def assert_identity(self, name, email, registration_number):
        rows = self.db.execute(self.sql).fetchall()
        self.assertEqual(2, len(rows), "Identity joins must not duplicate or drop payments")
        for row in rows:
            self.assertEqual(name, row["customer_name"])
            self.assertEqual(email, row["customer_email"])
            self.assertEqual(registration_number, row["registration_number"])

    async def test_delegate_details_take_precedence(self):
        self.registration()
        self.insert("delegate_registration_details", registration_id="registration", full_name="Delegate name", email="delegate@example.com")
        self.assert_identity("Delegate name", "delegate@example.com", "REG-TEST")

    async def test_registration_without_delegate_uses_participant_not_order_owner(self):
        self.insert("users", id="owner", full_name="Different buyer", email="buyer@example.com")
        self.registration()
        self.assert_identity("Registered participant", "registered@example.com", "REG-TEST")

    async def test_store_first_order_uses_owner_before_registration_exists(self):
        self.insert("users", id="owner", full_name="Store buyer", email="buyer@example.com")
        self.order()
        self.assert_identity("Store buyer", "buyer@example.com", None)

    async def test_blank_delegate_and_profile_fields_fall_back_to_account(self):
        self.registration(profile_name="  ")
        self.insert("delegate_registration_details", registration_id="registration", full_name="  ", email="  ")
        self.assert_identity("Account participant", "registered@example.com", "REG-TEST")

    async def test_owner_without_name_keeps_email(self):
        self.insert("users", id="owner", full_name="", email="buyer@example.com")
        self.order()
        self.assert_identity(None, "buyer@example.com", None)

    async def test_missing_identity_does_not_drop_transactions(self):
        self.order()
        self.assert_identity(None, None, None)


if __name__ == "__main__":
    unittest.main()
