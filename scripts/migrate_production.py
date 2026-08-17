"""Safely apply every committed Alembic migration to production.

Usage (from the repository root):
    python scripts/migrate_production.py --confirm-production

DATABASE_URL and APP_ENV are read from the normal application environment or
.env file. This script never embeds or prints database credentials.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.core.config import get_settings


REQUIRED_TABLES = {
    "alembic_version",
    "business_matching_profiles",
    "companies",
    "conversations",
    "delegate_packages",
    "direct_debit_bindings",
    "exhibitor_registrations",
    "messages",
    "orders",
    "payment_channels",
    "payment_webhook_events",
    "payments",
    "registrations",
    "users",
}


def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=PROJECT_ROOT, env=os.environ.copy(), check=True)


def sync_database_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-production",
        action="store_true",
        help="required acknowledgement that DATABASE_URL targets the intended production database",
    )
    parser.add_argument(
        "--skip-payment-channel-seed",
        action="store_true",
        help="skip the idempotent DOKU payment-channel catalog seed",
    )
    parser.add_argument(
        "--seed-all",
        action="store_true",
        help="also insert the complete idempotent IWBIF reference/demo dataset",
    )
    parser.add_argument(
        "--confirm-demo-data",
        action="store_true",
        help="required acknowledgement when --seed-all is used in production",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not args.confirm_production:
        parser.error("use --confirm-production after verifying DATABASE_URL and taking a database backup")
    if settings.APP_ENV.lower() != "production":
        parser.error("APP_ENV must be 'production' to prevent migration of the wrong database")
    if not settings.DATABASE_URL:
        parser.error("DATABASE_URL is not configured")
    if args.seed_all and not args.confirm_demo_data:
        parser.error("--seed-all requires --confirm-demo-data because it creates example users, payments, and messages")
    if args.seed_all and len(os.getenv("IWBIF_SEED_PASSWORD", "")) < 16:
        parser.error("--seed-all requires IWBIF_SEED_PASSWORD with at least 16 characters")

    alembic_config = Config(str(PROJECT_ROOT / "alembic.ini"))
    heads = ScriptDirectory.from_config(alembic_config).get_heads()
    if len(heads) != 1:
        parser.error(f"migration tree must have exactly one head; found: {', '.join(heads)}")
    expected_head = heads[0]
    print(f"Migration head: {expected_head}")

    # Connectivity is checked before any DDL is attempted.
    engine = create_engine(sync_database_url(settings.DATABASE_URL), pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("Database connection: OK")
    finally:
        engine.dispose()

    run(sys.executable, "-m", "alembic", "upgrade", "head")

    if not args.skip_payment_channel_seed:
        run(sys.executable, str(PROJECT_ROOT / "scripts" / "seed_payment_channels.py"))
    if args.seed_all:
        run(sys.executable, str(PROJECT_ROOT / "scripts" / "seed_iwbif_2026.py"))

    engine = create_engine(sync_database_url(settings.DATABASE_URL), pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            revisions = set(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
            table_names = set(inspect(connection).get_table_names())
        if revisions != {expected_head}:
            raise RuntimeError(f"database revision verification failed: {sorted(revisions)}")
        missing = sorted(REQUIRED_TABLES - table_names)
        if missing:
            raise RuntimeError(f"required tables are missing after migration: {', '.join(missing)}")
    finally:
        engine.dispose()

    print(f"SUCCESS: production database is at {expected_head}; required tables verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
