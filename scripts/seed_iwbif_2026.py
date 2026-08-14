"""Idempotently seed the IWBIF 2026 event and its database-backed parameters."""
import asyncio
from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.core.database import AsyncSessionFactory
from app.modules.events.models import Event, EventStatus
from app.modules.iwbif.models import BusinessMatchingSlot, DelegatePackage, EventActivity

EVENT_SLUG = "iwbif-2026"
ACTIVITIES = ["Business Forum", "Business Matching", "Conference", "Exhibition", "Networking Dinner", "Governor Dinner", "Trade Expo Indonesia", "Bandung Tour"]
PACKAGES = [("A", "Package A - USD500", Decimal("500")), ("B", "Package B - USD700", Decimal("700")), ("C", "Package C - USD370", Decimal("370"))]
SLOTS = [(date(2026, 10, 15), time(9), time(12), "15 Oct Morning"), (date(2026, 10, 15), time(13), time(17), "15 Oct Afternoon"), (date(2026, 10, 16), time(9), time(12), "16 Oct Morning"), (date(2026, 10, 16), time(13), time(17), "16 Oct Afternoon")]

async def seed():
    async with AsyncSessionFactory() as db:
        event = (await db.execute(select(Event).where(Event.slug == EVENT_SLUG))).scalar_one_or_none()
        jakarta = ZoneInfo("Asia/Jakarta")
        if not event:
            event = Event(name="International Women Business & Investment Forum 2026", slug=EVENT_SLUG, description="Empowering Women Entrepreneurs Through Finance, Global Collaboration, and Digital Transformation", venue_name="Hotel Kempinski Indonesia", venue_address="Jakarta, Indonesia", timezone="Asia/Jakarta", start_at=datetime(2026, 10, 14, tzinfo=jakarta), end_at=datetime(2026, 10, 17, 23, 59, tzinfo=jakarta), capacity=500, status=EventStatus.PUBLISHED)
            db.add(event); await db.flush()
        for code, name, amount in PACKAGES:
            if not (await db.execute(select(DelegatePackage.id).where(DelegatePackage.event_id == event.id, DelegatePackage.code == code))).first(): db.add(DelegatePackage(event_id=event.id, code=code, name=name, currency="USD", amount=amount))
        for name in ACTIVITIES:
            if not (await db.execute(select(EventActivity.id).where(EventActivity.event_id == event.id, EventActivity.name == name))).first(): db.add(EventActivity(event_id=event.id, name=name))
        for day, start, end, label in SLOTS:
            if not (await db.execute(select(BusinessMatchingSlot.id).where(BusinessMatchingSlot.event_id == event.id, BusinessMatchingSlot.label == label))).first(): db.add(BusinessMatchingSlot(event_id=event.id, slot_date=day, start_time=start, end_time=end, label=label, capacity=125))
        await db.commit(); print(f"Seeded {event.name} ({event.id})")

if __name__ == "__main__": asyncio.run(seed())
