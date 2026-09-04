"""add standalone USD 200 exhibitor package

Revision ID: 202609040043
Revises: 202609040042
"""
import uuid

import sqlalchemy as sa
from alembic import op


revision = "202609040043"
down_revision = "202609040042"
branch_labels = None
depends_on = None

PACKAGE_ID = uuid.UUID("49b27cc0-ec87-4de0-9768-c283148ae201")
RATE_ID = uuid.UUID("49b27cc0-ec87-4de0-9768-c283148ae202")
PRODUCT_ID = uuid.UUID("49b27cc0-ec87-4de0-9768-c283148ae203")


def upgrade() -> None:
    connection = op.get_bind()
    event_id = connection.execute(
        sa.text("SELECT id FROM events WHERE slug = :slug"), {"slug": "iwbif-2026"}
    ).scalar_one_or_none()
    if event_id is None:
        return

    existing = connection.execute(
        sa.text("SELECT id FROM delegate_packages WHERE event_id = :event_id AND code = :code"),
        {"event_id": event_id, "code": "EXHIBITOR"},
    ).scalar_one_or_none()
    if existing is not None:
        return

    connection.execute(sa.text("""
        INSERT INTO delegate_packages
            (id, event_id, code, name, package_type, selection_mode, description,
             display_order, currency, amount, payment_amount_idr, is_active)
        VALUES
            (:id, :event_id, 'EXHIBITOR', 'Exhibitor Package - USD200', 'exhibitor',
             'optional', 'Exhibitor access without requiring delegate registration',
             20, 'USD', 200, 3600000, true)
    """), {"id": PACKAGE_ID, "event_id": event_id})
    connection.execute(sa.text("""
        INSERT INTO delegate_package_rates
            (id, delegate_package_id, occupancy_type, name, amount, currency,
             payment_amount_idr, is_default, is_active)
        VALUES
            (:id, :package_id, 'standard', 'Exhibitor Access', 200, 'USD',
             3600000, true, true)
    """), {"id": RATE_ID, "package_id": PACKAGE_ID})
    connection.execute(sa.text("""
        INSERT INTO products
            (id, delegate_package_rate_id, event_id, code, name, description,
             product_type, price, currency, max_quantity, metadata_json, is_active)
        VALUES
            (:id, :rate_id, :event_id, 'EXHIBITOR_EXHIBITOR_STANDARD',
             'Exhibitor Package - USD200 - Exhibitor Access',
             'Exhibitor access without requiring delegate registration',
             'exhibitor', 3600000, 'IDR', 1,
             CAST(:metadata AS JSON), true)
    """), {
        "id": PRODUCT_ID,
        "rate_id": RATE_ID,
        "event_id": event_id,
        "metadata": '{"delegate_package_id":"%s","delegate_package_rate_id":"%s","package_type":"exhibitor","package_code":"EXHIBITOR","package_name":"Exhibitor Package - USD200","rate_name":"Exhibitor Access","occupancy_type":"standard","display_amount":"200","display_currency":"USD"}' % (PACKAGE_ID, RATE_ID),
    })


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("DELETE FROM products WHERE id = :id"), {"id": PRODUCT_ID})
    connection.execute(sa.text("DELETE FROM delegate_package_rates WHERE id = :id"), {"id": RATE_ID})
    connection.execute(sa.text("DELETE FROM delegate_packages WHERE id = :id"), {"id": PACKAGE_ID})
