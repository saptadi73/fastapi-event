"""Seed the payment-provider catalog; safe to re-run."""
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

# A script executed by path has `scripts/` as its import root; add the project
# root so `app.*` imports work from PowerShell and CI alike.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import AsyncSessionFactory
from app.modules.payments.models import PaymentChannel


CHANNELS = [
    ("doku", "QRIS", "qris", "QRIS", "DOKU_QRIS", 10),
    ("doku", "DANA", "e_wallet", "DANA", "DOKU_EWALLET_DANA", 20),
    ("doku", "OVO", "e_wallet", "OVO", "DOKU_EWALLET_OVO", 30),
    ("doku", "BCA", "virtual_account", "BCA Virtual Account", "DOKU_VA_BCA", 40),
    ("doku", "BNI", "virtual_account", "BNI Virtual Account", "DOKU_VA_BNI", 50),
    ("doku", "BRI", "virtual_account", "BRI Virtual Account", "DOKU_VA_BRI", 60),
    ("doku", "MANDIRI", "virtual_account", "Mandiri Virtual Account", "DOKU_VA_MANDIRI", 70),
    ("doku", "CIMB", "direct_debit", "CIMB Direct Debit", "DOKU_DIRECT_DEBIT_CIMB", 80),
    ("doku", "BRI_DIRECT_DEBIT", "direct_debit", "BRI Direct Debit", "DOKU_DIRECT_DEBIT_BRI", 90),
    ("doku", "MANDIRI_DIRECT_DEBIT", "direct_debit", "Mandiri Direct Debit", "DOKU_DIRECT_DEBIT_MANDIRI", 100),
    ("doku", "ALLO", "direct_debit", "Allo Bank Direct Debit", "DOKU_DIRECT_DEBIT_ALLO", 110),
    ("midtrans", "SNAP", "gateway", "Midtrans", "MIDTRANS_SNAP", 200),
]


async def main() -> None:
    async with AsyncSessionFactory() as session:
        for provider, code, category, name, config_key, sort_order in CHANNELS:
            item = (await session.execute(select(PaymentChannel).where(PaymentChannel.provider == provider, PaymentChannel.code == code))).scalar_one_or_none()
            if not item:
                session.add(PaymentChannel(provider=provider, code=code, category=category, display_name=name, config_key=config_key, is_enabled=False, sort_order=sort_order))
        await session.commit()
    print("Payment channel catalog seeded. Enable only providers configured with server-side credentials.")


if __name__ == "__main__":
    asyncio.run(main())
