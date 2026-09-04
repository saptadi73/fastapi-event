"""add Simplified Chinese translations for exhibitor and host packages

Revision ID: 202609040044
Revises: 202609040043
"""
import sqlalchemy as sa
from alembic import op

revision = "202609040044"
down_revision = "202609040043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("""
        INSERT INTO content_translations (id, entity_type, entity_id, locale, fields)
        SELECT gen_random_uuid(), 'delegate_package', p.id, 'zh-CN',
               CASE p.code
                 WHEN 'EXHIBITOR' THEN json_build_object('name', '参展商套餐 - 200美元', 'description', '无需注册成为代表即可获得参展商权限')
                 ELSE json_build_object('name', '主办方套餐', 'description', '主办方专属活动权限')
               END
        FROM delegate_packages p JOIN events e ON e.id = p.event_id
        WHERE e.slug = 'iwbif-2026' AND p.code IN ('EXHIBITOR', 'HOST', 'HOST_PACKAGE')
        ON CONFLICT (entity_type, entity_id, locale)
        DO UPDATE SET fields = EXCLUDED.fields, updated_at = now()
    """))
    connection.execute(sa.text("""
        INSERT INTO content_translations (id, entity_type, entity_id, locale, fields)
        SELECT gen_random_uuid(), 'delegate_package_rate', r.id, 'zh-CN',
               json_build_object('name', CASE p.code WHEN 'EXHIBITOR' THEN '参展商通行证' ELSE '主办方通行证' END)
        FROM delegate_package_rates r
        JOIN delegate_packages p ON p.id = r.delegate_package_id
        JOIN events e ON e.id = p.event_id
        WHERE e.slug = 'iwbif-2026' AND p.code IN ('EXHIBITOR', 'HOST', 'HOST_PACKAGE')
        ON CONFLICT (entity_type, entity_id, locale)
        DO UPDATE SET fields = EXCLUDED.fields, updated_at = now()
    """))
    connection.execute(sa.text("""
        INSERT INTO content_translations (id, entity_type, entity_id, locale, fields)
        SELECT gen_random_uuid(), 'product', product.id, 'zh-CN',
               json_build_object(
                 'name', CASE p.code WHEN 'EXHIBITOR' THEN '参展商套餐 - 200美元 - 参展商通行证' ELSE '主办方套餐 - 主办方通行证' END,
                 'description', CASE p.code WHEN 'EXHIBITOR' THEN '无需注册成为代表即可获得参展商权限' ELSE '主办方专属活动权限' END)
        FROM products product
        JOIN delegate_package_rates r ON r.id = product.delegate_package_rate_id
        JOIN delegate_packages p ON p.id = r.delegate_package_id
        JOIN events e ON e.id = p.event_id
        WHERE e.slug = 'iwbif-2026' AND p.code IN ('EXHIBITOR', 'HOST', 'HOST_PACKAGE')
        ON CONFLICT (entity_type, entity_id, locale)
        DO UPDATE SET fields = EXCLUDED.fields, updated_at = now()
    """))


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("""
        DELETE FROM content_translations t USING delegate_packages p, events e
        WHERE t.entity_type = 'delegate_package' AND t.entity_id = p.id AND t.locale = 'zh-CN'
          AND p.event_id = e.id AND e.slug = 'iwbif-2026' AND p.code IN ('EXHIBITOR', 'HOST', 'HOST_PACKAGE')
    """))
    connection.execute(sa.text("""
        DELETE FROM content_translations t USING delegate_package_rates r, delegate_packages p, events e
        WHERE t.entity_type = 'delegate_package_rate' AND t.entity_id = r.id AND t.locale = 'zh-CN'
          AND r.delegate_package_id = p.id AND p.event_id = e.id AND e.slug = 'iwbif-2026' AND p.code IN ('EXHIBITOR', 'HOST', 'HOST_PACKAGE')
    """))
    connection.execute(sa.text("""
        DELETE FROM content_translations t USING products product, delegate_package_rates r, delegate_packages p, events e
        WHERE t.entity_type = 'product' AND t.entity_id = product.id AND t.locale = 'zh-CN'
          AND product.delegate_package_rate_id = r.id AND r.delegate_package_id = p.id
          AND p.event_id = e.id AND e.slug = 'iwbif-2026' AND p.code IN ('EXHIBITOR', 'HOST', 'HOST_PACKAGE')
    """))
