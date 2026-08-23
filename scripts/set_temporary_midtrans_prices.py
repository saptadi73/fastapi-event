"""Set or restore temporary delegate prices for Midtrans production testing.

Examples, run from the repository root:
    python scripts/set_temporary_midtrans_prices.py
    python scripts/set_temporary_midtrans_prices.py --apply-test --confirm-production
    python scripts/set_temporary_midtrans_prices.py --restore --confirm-production

Without an action flag the script is read-only and only shows current values.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select, update


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.core.database import AsyncSessionFactory
from app.modules.iwbif.models import DelegatePackage
from app.modules.store.models import Product


TEST_PRICES = {
    "A": ("DELEGATE_A", Decimal("10000.00")),
    "B": ("DELEGATE_B", Decimal("11000.00")),
    "C": ("DELEGATE_C", Decimal("12000.00")),
}

ORIGINAL_PRICES = {
    "A": ("DELEGATE_A", Decimal("8000000.00")),
    "B": ("DELEGATE_B", Decimal("11200000.00")),
    "C": ("DELEGATE_C", Decimal("5920000.00")),
}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show, apply, or restore temporary Midtrans test prices."
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply-test", action="store_true")
    action.add_argument("--restore", action="store_true")
    parser.add_argument(
        "--confirm-production",
        action="store_true",
        help="required for writes when APP_ENV=production",
    )
    return parser.parse_args()


def database_label() -> str:
    url = get_settings().DATABASE_URL.replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )
    parsed = urlparse(url)
    return f"{parsed.hostname}:{parsed.port or 5432}/{parsed.path.lstrip('/')}"


async def current_values(session) -> tuple[dict, dict]:
    product_codes = [value[0] for value in TEST_PRICES.values()]
    products = (
        await session.execute(
            select(Product.code, Product.price, Product.currency)
            .where(Product.code.in_(product_codes))
            .order_by(Product.code)
        )
    ).all()
    packages = (
        await session.execute(
            select(DelegatePackage.code, DelegatePackage.payment_amount_idr)
            .where(DelegatePackage.code.in_(TEST_PRICES))
            .order_by(DelegatePackage.code)
        )
    ).all()
    return (
        {code: (Decimal(str(price)), currency) for code, price, currency in products},
        {code: Decimal(str(price)) for code, price in packages},
    )


async def main() -> None:
    args = arguments()
    settings = get_settings()
    target = TEST_PRICES if args.apply_test else ORIGINAL_PRICES
    write_requested = args.apply_test or args.restore

    print(f"Database: {database_label()}")
    print(f"APP_ENV: {settings.APP_ENV}")

    if write_requested and settings.APP_ENV.lower() == "production":
        if not args.confirm_production:
            raise SystemExit(
                "Production write refused: add --confirm-production after verifying DATABASE_URL."
            )

    async with AsyncSessionFactory() as session:
        before_products, before_packages = await current_values(session)
        print("Current products:", before_products)
        print("Current packages:", before_packages)

        if not write_requested:
            print("Dry run only; no data changed.")
            return

        expected_product_codes = {value[0] for value in target.values()}
        if set(before_products) != expected_product_codes or set(before_packages) != set(target):
            raise SystemExit("Required product/package masters are incomplete; no data changed.")

        for package_code, (product_code, price) in target.items():
            product_result = await session.execute(
                update(Product)
                .where(Product.code == product_code)
                .values(price=price, currency="IDR")
            )
            package_result = await session.execute(
                update(DelegatePackage)
                .where(DelegatePackage.code == package_code)
                .values(payment_amount_idr=price)
            )
            if product_result.rowcount != 1 or package_result.rowcount != 1:
                await session.rollback()
                raise SystemExit(
                    f"Non-unique or missing master {package_code}/{product_code}; all changes rolled back."
                )
        await session.commit()

    async with AsyncSessionFactory() as session:
        products, packages = await current_values(session)
        print("Updated products:", products)
        print("Updated packages:", packages)


if __name__ == "__main__":
    asyncio.run(main())
