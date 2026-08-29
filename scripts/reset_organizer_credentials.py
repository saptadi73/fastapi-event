"""Recover the IWBIF organizer account credentials.

This is an intentionally narrow production recovery tool. It updates one
existing organizer account and never creates a new user.
"""

import argparse
import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from app.core.database import AsyncSessionFactory, engine
from app.core.security import hash_password
from app.modules.users.models import User


TARGET_EMAIL = "organizer@iwbif.id"
TARGET_PASSWORD = "Iwbif2026J0$$"
LEGACY_EMAIL = "organizer@iwbif2026.org"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset the existing IWBIF organizer account credentials."
    )
    parser.add_argument(
        "--current-email",
        help=(
            "Current email of the organizer account. If omitted, the script "
            f"looks for {TARGET_EMAIL} and then {LEGACY_EMAIL}."
        ),
    )
    parser.add_argument(
        "--confirm-production",
        action="store_true",
        help="Required acknowledgement because this changes login credentials.",
    )
    return parser.parse_args()


async def reset(current_email: str | None) -> None:
    lookup_emails = (
        [current_email.lower()]
        if current_email
        else [TARGET_EMAIL, LEGACY_EMAIL]
    )

    async with AsyncSessionFactory() as db:
        rows = list(
            (
                await db.execute(
                    select(User).where(User.email.in_(lookup_emails)).with_for_update()
                )
            )
            .scalars()
            .all()
        )

        if not rows:
            raise RuntimeError(
                "Organizer account was not found. Pass its current email with "
                "--current-email; no user was changed."
            )
        if len(rows) > 1:
            raise RuntimeError(
                "Both target and legacy accounts exist. Pass the exact account "
                "to recover with --current-email; no user was changed."
            )

        organizer = rows[0]
        if organizer.role != "organizer":
            raise RuntimeError(
                f"Account {organizer.email} has role {organizer.role!r}, not "
                "'organizer'; no user was changed."
            )

        email_owner = await db.scalar(
            select(User).where(User.email == TARGET_EMAIL, User.id != organizer.id)
        )
        if email_owner is not None:
            raise RuntimeError(
                f"Target email {TARGET_EMAIL} is already used by another account; "
                "no user was changed."
            )

        organizer.email = TARGET_EMAIL
        organizer.password_hash = hash_password(TARGET_PASSWORD)
        organizer.status = "active"
        organizer.is_email_verified = True
        await db.commit()

        print(f"Organizer credentials reset successfully for {TARGET_EMAIL}.")
        print("The password was not printed. Rotate it after the first login.")


async def main() -> None:
    args = parse_args()
    if not args.confirm_production:
        raise SystemExit(
            "Refusing to change credentials without --confirm-production."
        )
    try:
        await reset(args.current_email)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
