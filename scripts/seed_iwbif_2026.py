"""Idempotent, relationally consistent demo dataset for IWBIF 2026."""
import asyncio
import hashlib
import html
import os
import sys
import zipfile
from datetime import date, datetime, time, timedelta
import re
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.database import AsyncSessionFactory, engine
from app.core.config import get_settings
from app.core.security import hash_password
from app.modules.business_matching.models import (
    AuditLog, BusinessMatchingProfile, Conversation, ConversationParticipant,
    MatchingSession, Meeting, MeetingResource, MeetingSlot, MeetingSlotProposal,
    MeetingStatus, MeetingVenue, Message, MessageType, Notification,
    ParticipantBlock, ParticipantReport,
)
from app.modules.check_ins.models import CheckIn
from app.modules.events.models import Event, EventStatus
from app.modules.iwbif.models import (
    AccommodationTravel, BusinessMatchingProfileSlot, BusinessMatchingSlot,
    Company, DelegatePackage, DelegatePackageFacility, DelegatePackageRate, DelegateRegistrationDetail, EventActivity,
    ExhibitorRegistration, RegistrationActivity, RegistrationDocument,
    RegistrationParticipationCategory,
)
from app.modules.participants.models import ParticipantProfile
from app.modules.payments.models import Order, OrderStatus, Payment, PaymentStatus, PaymentWebhookEvent
from app.modules.registrations.models import Registration, RegistrationStatus
from app.modules.sessions.models import EventSession
from app.modules.speakers.models import EventSpeaker, Speaker
from app.modules.store.models import Product
from app.modules.tickets.models import QRToken, Ticket, TicketStatus
from app.modules.users.models import User

TZ = ZoneInfo("Asia/Jakarta")
EVENT_SLUG = "iwbif-2026"
ACTIVITIES = ["Business Forum", "Business Matching", "Conference", "Exhibition", "Networking Dinner", "Governor Dinner", "Trade Expo Indonesia", "Bandung Tour"]
# Demo-only fixed IDR charges (illustrative 1 USD = IDR 16,000). Organizer must
# approve production amounts independently from the USD display prices.
PACKAGES = [("A", "Package A - USD500", Decimal("500"), Decimal("8000000")), ("B", "Package B - USD700", Decimal("700"), Decimal("11200000")), ("C", "Package C - USD370", Decimal("370"), Decimal("5920000"))]
PROFILE_SLOTS = [(date(2026, 10, 15), time(9), time(12), "15 Oct Morning"), (date(2026, 10, 15), time(13), time(17), "15 Oct Afternoon"), (date(2026, 10, 16), time(9), time(12), "16 Oct Morning"), (date(2026, 10, 16), time(13), time(17), "16 Oct Afternoon")]

DELEGATES = [
    ("sari@nusantarafoods.id", "Dr. Sari Wulandari", "Nusantara Foods", "CEO", "Indonesia", "Food & Beverage", "A", ["Buyer", "Distributor"], ["Malaysia", "Singapore"], ["Spices", "Packaged Food"], ["Retail Distribution", "Import"]),
    ("mei.lin@dragonretail.cn", "Mei Lin", "Dragon Retail Group", "Procurement Director", "China", "Trading", "B", ["Importer", "Supplier"], ["Indonesia", "Malaysia"], ["Retail", "Consumer Products"], ["Indonesian Products", "Food Supplier"]),
    ("aisha@amanahcapital.my", "Aisha Rahman", "Amanah Impact Capital", "Investment Partner", "Malaysia", "Finance", "B", ["Investor", "Joint Venture"], ["Indonesia", "Singapore"], ["Impact Investment", "Women-led MSMEs"], ["Investment Pipeline", "Joint Venture"]),
    ("clara@auroradigital.sg", "Clara Tan", "Aurora Digital Commerce", "Founder", "Singapore", "Technology", "C", ["Technology Partner", "Buyer"], ["Indonesia", "Vietnam"], ["Digital Commerce", "SaaS"], ["MSME Partners", "Market Expansion"]),
    ("maria@pacificwellness.ph", "Maria Santos", "Pacific Wellness", "Managing Director", "Philippines", "Healthcare", "A", ["Distributor", "Investor"], ["Indonesia", "Malaysia"], ["Wellness", "Natural Products"], ["Distribution", "Manufacturing Partner"]),
]


def extract_text_from_docx(docx_path: str | Path) -> str:
    with zipfile.ZipFile(docx_path, "r") as zf:
        data = zf.read("word/document.xml")
    text = html.unescape(data.decode("utf-8"))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_package_code(raw: str) -> str:
    value = re.sub(r"\s+", " ", raw).strip()
    value = re.sub(r"[^A-Z0-9_ -]", "", value.upper())
    return re.sub(r"[\s-]+", " ", value).replace(" ", "_").strip("_")[:30] or "PACKAGE"


def parse_delegate_packages_from_docx(docx_path: str | Path) -> list[tuple[str, str, Decimal, Decimal | None]]:
    text = extract_text_from_docx(docx_path)
    matches = re.finditer(
        r"\bDELEGATE\s+PACKAGE\s+([A-Za-z0-9]+)\b(.*?)(?=\bDELEGATE\s+PACKAGE\b|$)",
        text,
        re.IGNORECASE,
    )
    packages: list[tuple[str, str, Decimal, Decimal | None]] = []
    for match in matches:
        raw_code = match.group(1).strip()
        code = normalize_package_code(raw_code)
        details = match.group(2)
        usd_match = re.search(r"(?:USD|US\$|\$)\s*([0-9][0-9,]*(?:\.[0-9]+)?)", details, re.IGNORECASE)
        if usd_match is None:
            continue
        amount = Decimal(usd_match.group(1).replace(",", ""))
        idr_match = re.search(r"(?:IDR|Rp\.?|Rupiah)\s*([0-9][0-9.,]*)", details, re.IGNORECASE)
        payment_amount_idr = Decimal(re.sub(r"[^0-9]", "", idr_match.group(1))) if idr_match else None
        name = f"Delegate Package {raw_code.strip()}"
        packages.append((code[:30], name, amount, payment_amount_idr))
    return packages

async def one(db, model, **where):
    return (await db.execute(select(model).filter_by(**where).limit(1))).scalar_one_or_none()

async def ensure(db, model, defaults=None, **where):
    row = await one(db, model, **where)
    if row:
        for key, value in (defaults or {}).items(): setattr(row, key, value)
        return row
    row = model(**where, **(defaults or {})); db.add(row); await db.flush(); return row

async def ensure_user(db, *, email, password_hash, defaults):
    """Create seed users without resetting passwords of existing accounts."""
    row = await one(db, User, email=email)
    if row:
        for key, value in defaults.items():
            if key != "password_hash":
                setattr(row, key, value)
        return row
    row = User(email=email, password_hash=password_hash, **defaults)
    db.add(row); await db.flush(); return row

def at(day, hour=0, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=TZ)

async def seed():
    settings = get_settings()
    seed_password = os.getenv("IWBIF_SEED_PASSWORD", "")
    if settings.APP_ENV.lower() == "production":
        if len(seed_password) < 16:
            raise RuntimeError("IWBIF_SEED_PASSWORD (minimum 16 characters) is required for production seed data")
        if seed_password == "IwbifDemo2026!":
            raise RuntimeError("the documented demo password is forbidden in production")
    elif not seed_password:
        seed_password = "IwbifDemo2026!"

    async with AsyncSessionFactory() as db:
        event = await ensure(db, Event, slug=EVENT_SLUG, defaults=dict(name="International Women Business & Investment Forum 2026", description="Empowering Women Entrepreneurs Through Finance, Global Collaboration, and Digital Transformation", venue_name="Hotel Indonesia Kempinski Jakarta", venue_address="Jl. M.H. Thamrin No. 1, Jakarta", timezone="Asia/Jakarta", start_at=at(14), end_at=at(17, 23, 59), capacity=500, status=EventStatus.PUBLISHED))

        # Preserve existing foreign-key references while aligning the activity
        # master with the implementation reference document.
        legacy_activity = await one(db, EventActivity, event_id=event.id, name="Industrial Visit")
        documented_activity = await one(db, EventActivity, event_id=event.id, name="Bandung Tour")
        if legacy_activity is not None and documented_activity is None:
            legacy_activity.name = "Bandung Tour"

        packages_by_code = {}
        source_docx = Path(__file__).with_name("..") / "docs" / "iwapi-iwbif_package.docx"
        source_docx = source_docx.resolve()
        seed_packages = parse_delegate_packages_from_docx(source_docx) if source_docx.exists() else []
        base_packages = seed_packages or PACKAGES

        fallback_idr = {code: payment_amount_idr for code, _, _, payment_amount_idr in PACKAGES}
        excel_prices = {"A": (Decimal("500"), Decimal("700")), "B": (Decimal("400"), Decimal("550"))}
        for package_spec in base_packages:
            code, name, amount, payment_amount_idr = package_spec
            if code in excel_prices: amount = excel_prices[code][0]
            payment_amount_idr = payment_amount_idr if payment_amount_idr is not None else fallback_idr.get(code)
            packages_by_code[code] = await ensure(db, DelegatePackage, event_id=event.id, code=code, defaults=dict(name=name, package_type="main", selection_mode="required_one", display_order=1 if code == "A" else 2, currency="USD", amount=amount, payment_amount_idr=payment_amount_idr, is_active=code in {"A", "B"}))
        bandung = await ensure(db, DelegatePackage, event_id=event.id, code="TRIP_BANDUNG", defaults=dict(name="Additional Trip to Bandung", package_type="additional", selection_mode="optional", description="Optional Bandung trip", display_order=10, currency="USD", amount=Decimal("200"), payment_amount_idr=None, is_active=True))
        packages_by_code["TRIP_BANDUNG"] = bandung
        rate_specs = {"A": [("sharing", "Twin Sharing Basis", Decimal("500"), True), ("single", "Single Room", Decimal("700"), False)], "B": [("sharing", "Twin Sharing Basis", Decimal("400"), True), ("single", "Single Room", Decimal("550"), False)], "TRIP_BANDUNG": [("sharing", "Twin Sharing Basis", Decimal("200"), True), ("single", "Single Room", Decimal("300"), False)]}
        for code, specs in rate_specs.items():
            delegate_package = packages_by_code[code]
            for occupancy, rate_name, amount, is_default in specs:
                rate = await ensure(db, DelegatePackageRate, delegate_package_id=delegate_package.id, occupancy_type=occupancy, defaults=dict(name=rate_name, amount=amount, currency="USD", payment_amount_idr=delegate_package.payment_amount_idr if occupancy == "sharing" else None, is_default=is_default, is_active=True))
                payable_amount = rate.payment_amount_idr if rate.payment_amount_idr is not None else rate.amount
                payable_currency = "IDR" if rate.payment_amount_idr is not None else rate.currency
                await ensure(db, Product, delegate_package_rate_id=rate.id, defaults=dict(event_id=event.id, code=f"DELEGATE_{code}_{occupancy.upper()}", name=f"{delegate_package.name} - {rate_name}", description=delegate_package.description, product_type="delegate" if delegate_package.package_type == "main" else "additional", price=payable_amount, currency=payable_currency, max_quantity=1, metadata_json={"delegate_package_id": str(delegate_package.id), "delegate_package_rate_id": str(rate.id), "package_type": delegate_package.package_type, "package_code": delegate_package.code, "package_name": delegate_package.name, "rate_name": rate_name, "occupancy_type": occupancy, "display_amount": str(amount), "display_currency": "USD"}, is_active=True))
        facilities = {
            "A": ["3 Nights Accommodation at 5 star hotel Jakarta", "Airport Transfers", "Local Transportation", "Conference Access & Pass to TEI - Trade Expo Indonesia", "2 lunches & 2 coffee breaks", "Welcome Dinner at PIK2", "Welcome Dinner hosted by Governor of DKI Jakarta", "Jakarta City Tour"],
            "B": ["3 Nights Accommodation at 3/5 star hotel Jakarta", "Airport Transfers", "Local Transportation", "Conference Access & Pass to TEI - Trade Expo Indonesia", "2 lunches & 2 coffee breaks", "Welcome Dinner at PIK2", "Welcome Dinner hosted by Governor of DKI Jakarta", "Jakarta City Tour"],
            "TRIP_BANDUNG": ["Accommodation at 4 star hotel Bandung", "Airport Transfers", "Local Transportation", "Meals As the Program", "Destination at Bandung", "Bandung City Tour", "Visiting Jababeka Industry"],
        }
        for code, names in facilities.items():
            for position, facility_name in enumerate(names, 1):
                await ensure(db, DelegatePackageFacility, delegate_package_id=packages_by_code[code].id, name=facility_name, defaults=dict(pricing_mode="included", currency="USD", display_order=position, is_active=True))
        activity = {}
        for name in ACTIVITIES: activity[name] = await ensure(db, EventActivity, event_id=event.id, name=name, defaults=dict(is_active=True))
        profile_slots = []
        for day, start, end, label in PROFILE_SLOTS:
            profile_slots.append(await ensure(db, BusinessMatchingSlot, event_id=event.id, label=label, defaults=dict(slot_date=day, start_time=start, end_time=end, capacity=125, is_active=True)))

        password = hash_password(seed_password)
        admin = await ensure_user(db, email="organizer@iwbif2026.org", password_hash=password, defaults=dict(full_name="IWBIF 2026 Organizer", phone="+6281100002026", country="Indonesia", status="active", role="organizer", is_email_verified=True))
        users, participants, registrations, profiles = [], [], [], []
        activity_ids = [str(x.id) for x in activity.values()]
        for idx, (email, full_name, company, job, country, sector, package_code, looking, preferred, interests, needs) in enumerate(DELEGATES, 1):
            user = await ensure_user(db, email=email, password_hash=password, defaults=dict(full_name=full_name, phone=f"+628120026{idx:04d}", country=country, status="active", role="participant", is_email_verified=True))
            participant = await ensure(db, ParticipantProfile, user_id=user.id, defaults=dict(full_name=full_name, organization_name=company, biography=f"{job} at {company}, focused on cross-border women-led business growth.", profile_photo_url=f"https://ui-avatars.com/api/?name={full_name.replace(' ', '+')}"))
            company_row = await ensure(db, Company, participant_id=participant.id, defaults=dict(name=company, country=country, address=f"Business District, {country}", website=f"https://{company.lower().replace(' ', '')}.example"))
            reg = await ensure(db, Registration, event_id=event.id, participant_id=participant.id, defaults=dict(registration_number=f"IWBIF26-{idx:04d}", status=RegistrationStatus.CONFIRMED, dietary_preference="Halal meal", accessibility_requirements=None, emergency_contact_name=f"Emergency Contact {idx}", emergency_contact_phone=f"+628139900{idx:04d}", consent_snapshot="terms:v1;privacy:v1;business_matching:v1", confirmed_at=at(1 + idx, 9)))
            categories = ["Delegate", "Buyer" if "Buyer" in looking else "Investor"]
            await ensure(db, DelegateRegistrationDetail, registration_id=reg.id, defaults=dict(company_id=company_row.id, delegate_package_id=packages_by_code[package_code].id, full_name=full_name, job_title=job, company_organization=company, nationality=country, title="Dr" if full_name.startswith("Dr.") else "Ms", business_sector=sector, email=email, office_phone=None, company_website=f"https://{company.lower().replace(' ', '')}.example", linkedin="https://www.linkedin.com/", company_address=f"Business District, {country}", participation_categories=categories, presentation_topic=None, products_interested="Cross-border women-led products", investment_interest="Sustainable growth opportunities", room_preference="Twin Sharing", preferred_roommate=None, arrival_date=date(2026, 10, 14), departure_date=date(2026, 10, 17), flight_number=f"IW{100+idx}", airport="CGK", need_airport_pickup=True, products_services=f"Products and services from {company}", looking_for=looking, preferred_countries=preferred, business_objectives="Establish qualified partnerships and documented deal pipeline", activity_ids=activity_ids, dietary_restrictions="Halal", medical_condition=None, special_assistance=None, need_official_invoice=True, tax_id=f"TAX-IWBIF-{idx:04d}", information_accuracy_confirmed=True, terms_accepted=True, business_matching_data_consent=True, terms_version="v1", consent_version="v1", terms_accepted_at=at(1, 8), consent_accepted_at=at(1, 8), submitted_at=at(1, 8, 30)))
            await ensure(db, AccommodationTravel, registration_id=reg.id, defaults=dict(room_preference="Twin Sharing", preferred_roommate=None, arrival_date=date(2026, 10, 14), departure_date=date(2026, 10, 17), flight_number=f"IW{100+idx}", airport="CGK", need_airport_pickup=True))
            for category in categories: await ensure(db, RegistrationParticipationCategory, registration_id=reg.id, category=category)
            for activity_id in activity.values(): await ensure(db, RegistrationActivity, registration_id=reg.id, activity_id=activity_id.id)
            selected_slot = profile_slots[idx % len(profile_slots)]
            bm = await ensure(db, BusinessMatchingProfile, event_id=event.id, participant_id=participant.id, defaults=dict(registration_id=reg.id, company_id=company_row.id, organization_name=company, country_code={"Indonesia":"IDN","China":"CHN","Malaysia":"MYS","Singapore":"SGP","Philippines":"PHL"}[country], organization_type="Women-led Enterprise", position_title=job, short_description=f"{company} business profile for IWBIF 2026", target_market=preferred, preferred_regions=preferred, business_interests=interests, business_sectors=[sector], technology_interests=["Digital Commerce"] if sector == "Technology" else [], partnership_types=["Distribution", "Investment", "Joint Venture"], business_offerings=interests, business_needs=needs, representative=full_name, contact_email=email, contact_phone=user.phone, products=f"Products offered by {company}", services=f"Services offered by {company}", hs_code=f"HS-{idx:04d}", production_capacity="Scalable regional capacity", certificates="ISO / applicable national certification", markets_served=", ".join(preferred), preferred_slot_ids=[str(selected_slot.id)], estimated_deal_investment_value=f"USD {100000 * idx:,}", additional_notes="Available for curated meetings", profile_sharing_consent=True, profile_sharing_consent_at=at(2), available_for_matching=True, allow_messages=True, allow_meeting_requests=True))
            await ensure(db, BusinessMatchingProfileSlot, profile_id=bm.id, slot_id=selected_slot.id)
            idr_amount = packages_by_code[package_code].payment_amount_idr
            order = await ensure(db, Order, registration_id=reg.id, order_number=f"ORD-IWBIF26-{idx:04d}", defaults=dict(user_id=user.id, subtotal=idr_amount, discount_amount=0, tax_amount=0, service_fee=0, total_amount=idr_amount, currency="IDR", status=OrderStatus.PAID, expires_at=at(10)))
            va_no = f"8808{idx:012d}"
            seeded_payment = await ensure(db, Payment, order_id=order.id, defaults=dict(provider="doku", provider_transaction_id=f"DOKU-EXT-IWBIF26-{idx:04d}", provider_order_id=order.order_number, payment_type="doku_snap_va", channel_code="BCA", virtual_account_no=va_no, gross_amount=order.total_amount, currency="IDR", transaction_status=PaymentStatus.SUCCESS, fraud_status=None, raw_response='{"provider":"doku_snap_va","seed":true}', paid_at=at(3 + idx), expired_at=None, checkout_url=None))
            await ensure(db, PaymentWebhookEvent, provider="doku_snap_va", request_id=f"DOKU-NOTIFY-IWBIF26-{idx:04d}", defaults=dict(payment_id=seeded_payment.id, event_status="SUCCESS", payload={"virtualAccountNo":va_no,"trxId":order.order_number,"paidAmount":{"value":str(order.total_amount),"currency":"IDR"}}))
            ticket = await ensure(db, Ticket, registration_id=reg.id, defaults=dict(ticket_number=f"TCK-IWBIF26-{idx:04d}", status=TicketStatus.ISSUED))
            await ensure(db, QRToken, ticket_id=ticket.id, token_hash=hashlib.sha256(f"IWBIF26-{idx:04d}".encode()).hexdigest(), defaults=dict(expires_at=at(18), is_active=True))
            if idx <= 2: await ensure(db, CheckIn, ticket_id=ticket.id, event_id=event.id, defaults=dict(session_id=None, check_in_type="qr", check_in_at=at(16, 7, 30 + idx), check_in_by=admin.id, gate_name="Kempinski Main Lobby", device_id="IWBIF-SEED-01", status="success", notes="Delegate arrival check-in"))
            users.append(user); participants.append(participant); registrations.append(reg); profiles.append(bm)

        # Nine featured profiles represent every speaker category described in
        # docs/IWAPI_SUMMIT_WEBSITE.md. Names other than the minister are demo data.
        speakers = [
            ("Arifah Choiri Fauzi", "Minister of Women Empowerment", "Government of Indonesia", "IDN", ["Women Empowerment", "Public Policy"], "Keynote: Strengthening Women Entrepreneurship", "/uploads/speakers/arifah-choiri-fauzi.jpg"),
            ("Dr. Ratna Kusuma", "Chairwoman", "IWAPI", "IDN", ["Women Entrepreneurship", "Global Trade", "Business Associations"], "Opening Remarks: Women-Led Business Networks", "/uploads/speakers/ratna-kusuma.jpg"),
            ("Linda Chen", "Regional Investment Director", "Asia Growth Fund", "SGP", ["Investment", "Access to Finance"], "Panel: Access to Finance and Investment", "/uploads/speakers/linda-chen.jpg"),
            ("Maya Santoso", "Women Business Leader", "Nusantara Women Enterprise", "IDN", ["Women Business Leadership", "MSME Growth"], "Panel: Scaling Women-Led Enterprises", None),
            ("Sofia Martinez", "International Entrepreneur", "Global Women Trade Network", "ESP", ["International Entrepreneurship", "Market Expansion"], "Panel: Cross-Border Market Expansion", None),
            ("Amina Okafor", "Impact Investor", "Women Growth Capital", "NGA", ["Impact Investment", "Investment Readiness"], "Strategic Discussion: Investment Readiness", None),
            ("Priya Nair", "Director of SME Banking", "Regional Development Bank", "IND", ["Financial Inclusion", "SME Banking"], "Panel: Inclusive Finance for Women-Owned MSMEs", None),
            ("Dr. Elena Petrova", "Digital Commerce Expert", "Digital Commerce Institute", "BGR", ["Digital Transformation", "E-Commerce"], "Panel: Digital Transformation and Global Reach", None),
            ("Grace Wong", "International Business Mentor", "Asia-Pacific Mentors Network", "MYS", ["International Mentoring", "Strategic Partnerships"], "Mentoring Session: Building Strategic Partnerships", None),
        ]
        for name, title, org, country, expertise, session_title, photo_url in speakers:
            # Rename the original generic minister record in existing seeded databases.
            speaker = await one(db, Speaker, full_name=name)
            if speaker is None and name == "Arifah Choiri Fauzi":
                speaker = await one(db, Speaker, full_name="H.E. Minister of Women Empowerment")
                if speaker is not None:
                    speaker.full_name = name
            defaults = dict(
                professional_title=title,
                organization_name=org,
                country_code=country,
                biography=f"{name} brings strategic perspectives to IWBIF 2026.",
                profile_photo_url=photo_url or f"https://ui-avatars.com/api/?name={name.replace(' ', '+')}",
                linkedin_url="https://www.linkedin.com/",
                website_url="https://iwbif2026.org",
                expertise_tags=expertise,
                session_title=session_title,
                is_featured=True,
                status="published",
            )
            if speaker is None:
                speaker = Speaker(full_name=name, **defaults)
                db.add(speaker)
                await db.flush()
            else:
                for key, value in defaults.items():
                    setattr(speaker, key, value)
            await ensure(db, EventSpeaker, event_id=event.id, speaker_id=speaker.id)

        program = [
            ("opening-ceremony", "Opening Ceremony", "ceremony", 16, 8, 30, 60),
            ("women-led-global-trade", "Women-Led Businesses in Global Trade", "keynote", 16, 9, 30, 60),
            ("access-to-finance", "Access to Finance and Investment", "panel", 16, 10, 45, 75),
            ("curated-business-matching", "Curated Business Matching", "business_matching", 16, 13, 0, 180),
            ("governor-dinner", "Governor Dinner", "networking", 16, 19, 0, 120),
            ("jababeka-industrial-visit", "Jababeka Industrial Visit", "industrial_visit", 17, 9, 0, 180),
        ]
        for slug, title, kind, day, hour, minute, duration in program:
            await ensure(db, EventSession, event_id=event.id, slug=slug, defaults=dict(title=title, description=f"{title} — official IWBIF 2026 program.", session_type=kind, room_name="Bali Room" if day == 16 else "Jababeka Industrial Estate", start_at=at(day, hour, minute), end_at=at(day, hour, minute) + timedelta(minutes=duration), capacity=500, status="scheduled"))

        exhibitor_company = await one(db, Company, participant_id=participants[0].id)
        exhibitor = await ensure(db, ExhibitorRegistration, event_id=event.id, participant_id=participants[0].id, defaults=dict(company_id=exhibitor_company.id, company_name="Nusantara Foods", brand="Rasa Nusantara", contact_person="Dr. Sari Wulandari", email=users[0].email, products_to_display="Premium spices and packaged foods", booth_size_requested="Standard Booth 3x3", electricity_requirement="Standard 220V", special_requirement="Food sampling table", exhibition_terms_accepted=True, exhibition_terms_version="v1", exhibition_terms_accepted_at=at(2), status="submitted"))
        private_root = Path(".private_uploads").resolve(); (private_root / "seed").mkdir(parents=True, exist_ok=True)
        for reg, dtype, filename in [(registrations[0], "PASSPORT_COPY", "passport-demo.pdf"), (registrations[0], "COMPANY_PROFILE", "company-profile-demo.pdf")]:
            path = private_root / "seed" / filename
            if not path.exists(): path.write_bytes(b"IWBIF 2026 DEMO DOCUMENT\n")
            await ensure(db, RegistrationDocument, registration_id=reg.id, document_type=dtype, defaults=dict(exhibitor_id=None, original_filename=filename, storage_key=f"seed/{filename}", mime_type="application/pdf", file_size=path.stat().st_size))
        catalogue = private_root / "seed" / "product-catalogue-demo.pdf"
        if not catalogue.exists(): catalogue.write_bytes(b"IWBIF 2026 DEMO CATALOGUE\n")
        await ensure(db, RegistrationDocument, exhibitor_id=exhibitor.id, document_type="PRODUCT_CATALOGUE", defaults=dict(registration_id=None, original_filename=catalogue.name, storage_key=f"seed/{catalogue.name}", mime_type="application/pdf", file_size=catalogue.stat().st_size))

        matching_session = await ensure(db, MatchingSession, event_id=event.id, name="IWBIF Curated Meetings", defaults=dict(session_date=date(2026, 10, 16), start_time=time(13), end_time=time(17), slot_duration_minutes=30, status="active"))
        meeting_slots = []
        for hour, minute in [(13,0),(13,30),(14,0),(14,30)]:
            start = at(16, hour, minute); meeting_slots.append(await ensure(db, MeetingSlot, matching_session_id=matching_session.id, starts_at=start, defaults=dict(ends_at=start + timedelta(minutes=30), status="available")))
        venue = await ensure(db, MeetingVenue, event_id=event.id, name="IWBIF Deal Room", defaults=dict(location_description="Bali Room, Hotel Indonesia Kempinski"))
        resources = []
        for idx in range(1, 4): resources.append(await ensure(db, MeetingResource, venue_id=venue.id, code=f"TABLE-{idx:02d}", defaults=dict(resource_type="table", name=f"Business Matching Table {idx}", capacity=4, is_active=True)))

        conv = await ensure(db, Conversation, event_id=event.id, created_by=participants[0].id, defaults=dict(status="active", last_message_at=at(10, 10)))
        for participant in participants[:2]: await ensure(db, ConversationParticipant, conversation_id=conv.id, participant_id=participant.id, defaults=dict(last_read_at=at(10, 10), is_archived=False, is_muted=False))
        await ensure(db, Message, conversation_id=conv.id, sender_participant_id=participants[0].id, body="Hello, I would like to discuss distribution opportunities at IWBIF 2026.", defaults=dict(message_type=MessageType.TEXT, meeting_id=None, reply_to_message_id=None))
        meeting = await ensure(db, Meeting, event_id=event.id, requester_participant_id=participants[0].id, recipient_participant_id=participants[1].id, topic="Indonesia–China Food Distribution", defaults=dict(conversation_id=conv.id, purpose="distribution", description="Explore import and retail distribution partnership", status=MeetingStatus.CONFIRMED, confirmed_slot_id=meeting_slots[0].id, venue_resource_id=resources[0].id, confirmed_at=at(10, 11)))
        await ensure(db, MeetingSlotProposal, meeting_id=meeting.id, slot_id=meeting_slots[0].id, defaults=dict(proposed_by=participants[0].id, status="accepted"))
        await ensure(db, Message, conversation_id=conv.id, sender_participant_id=participants[0].id, body="Meeting confirmed at Business Matching Table 1.", defaults=dict(message_type=MessageType.MEETING_CONFIRMED, meeting_id=meeting.id, reply_to_message_id=None))
        await ensure(db, Notification, user_id=users[1].id, event_id=event.id, type="meeting_confirmed", defaults=dict(title="Meeting confirmed", body="Indonesia–China Food Distribution", entity_type="meeting", entity_id=meeting.id, is_read=False, read_at=None))
        await ensure(db, AuditLog, event_id=event.id, actor_user_id=users[0].id, action="meeting_confirmed", entity_type="meeting", entity_id=meeting.id, defaults=dict(old_values={"status":"accepted"}, new_values={"status":"confirmed"}))
        await ensure(db, ParticipantBlock, event_id=event.id, blocker_id=participants[3].id, blocked_id=participants[4].id)
        await ensure(db, ParticipantReport, event_id=event.id, reporter_id=participants[4].id, reported_id=participants[3].id, defaults=dict(reason="Inaccurate company information", details="Demo moderation case", status="open"))

        await db.commit()
        print(f"Seeded complete IWBIF dataset for event {event.id}")
        print("Seed accounts created. Password is sourced from IWBIF_SEED_PASSWORD and is not displayed.")
    await engine.dispose()

if __name__ == "__main__": asyncio.run(seed())
