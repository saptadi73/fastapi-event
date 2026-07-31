import asyncio
import hashlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import AsyncSessionFactory, engine
from app.core.security import hash_password
from app.modules.check_ins.models import CheckIn
from app.modules.events.models import Event, EventStatus
from app.modules.participants.models import ParticipantProfile
from app.modules.payments.models import Order, OrderStatus, Payment, PaymentStatus
from app.modules.registrations.models import Registration, RegistrationStatus
from app.modules.sessions.models import EventSession
from app.modules.speakers.models import Speaker
from app.modules.ticket_types.models import TicketType
from app.modules.tickets.models import QRToken, Ticket, TicketStatus
from app.modules.users.models import User
from app.modules.workshop_tracks.models import WorkshopTrack


def utc_at(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


async def get_one(session, model, **filters):
    stmt = select(model).filter_by(**filters).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_or_create(session, model, defaults: dict[str, Any] | None = None, **filters):
    row = await get_one(session, model, **filters)
    if row:
        for key, value in (defaults or {}).items():
            setattr(row, key, value)
        await session.flush()
        return row, False

    row = model(**filters, **(defaults or {}))
    session.add(row)
    await session.flush()
    return row, True


def qr_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def seed() -> None:
    async with AsyncSessionFactory() as session:
        password = hash_password("Password123!")

        admin, _ = await get_or_create(
            session,
            User,
            email="admin@aseanaiedu.com",
            defaults={
                "password_hash": password,
                "full_name": "ASEAN AI Education Summit Admin",
                "phone": "+6281200000001",
                "status": "active",
                "is_email_verified": True,
            },
        )

        event, _ = await get_or_create(
            session,
            Event,
            slug="asean-ai-for-education-summit-2026",
            defaults={
                "name": "ASEAN AI for Education Summit 2026",
                "description": (
                    "A two-day international summit and hands-on workshop connecting "
                    "technology professionals, educators, researchers, and institutions "
                    "to create practical AI solutions for students and schools across Southeast Asia."
                ),
                "venue_name": "Jakarta Convention Center",
                "venue_address": "Jakarta Convention Center, Jakarta, Indonesia",
                "timezone": "Asia/Bangkok",
                "start_at": utc_at(2026, 11, 18, 0, 30),
                "end_at": utc_at(2026, 11, 19, 11, 0),
                "capacity": 300,
                "status": EventStatus.PUBLISHED,
            },
        )

        tracks_data = [
            ("Track A - AI Learning Assistant", "Build a conversational learning assistant using LLM integration, RAG, educational content management, and response validation.", 70, 1),
            ("Track B - AI Student Assessment", "Create an intelligent assessment platform with rubric-based evaluation, feedback generation, and learning recommendations.", 60, 2),
            ("Track C - Multilingual Education AI", "Build multilingual learning tools for ASEAN languages with translation workflows, speech features, and content localization.", 60, 3),
            ("Track D - AI Analytics for Schools", "Develop dashboards and predictive tools for attendance, engagement, academic performance, and school operations.", 55, 4),
            ("Track E - Inclusive Education Technology", "Design accessible AI-assisted learning solutions for students with disabilities or limited access to education resources.", 55, 5),
        ]
        tracks = {}
        for name, description, capacity, order_index in tracks_data:
            track, _ = await get_or_create(
                session,
                WorkshopTrack,
                event_id=event.id,
                name=name,
                defaults={
                    "description": description,
                    "capacity": capacity,
                    "order_index": order_index,
                },
            )
            tracks[name] = track

        ticket_types_data = [
            ("STUDENT", "Student Pass", "Two-day access, keynote and panel sessions, technical workshop participation, materials, networking access, meals, certificate, participant directory, and QR ticket.", 79, 80),
            ("DEVELOPER", "Developer Pass", "Standard pass for developers, engineers, researchers, and technology professionals with all sessions, workshop track, networking night, certificate, and QR ticket.", 149, 140),
            ("PROFESSIONAL", "Professional Pass", "Premium access for managers, founders, institutional representatives, and senior professionals with priority check-in and executive networking.", 249, 60),
            ("TEAM", "Team Pass", "Team package for companies, universities, startups, and institutions registering five participants.", 599, 20),
        ]
        ticket_types = {}
        for code, name, description, price, capacity in ticket_types_data:
            ticket_type, _ = await get_or_create(
                session,
                TicketType,
                event_id=event.id,
                code=code,
                defaults={
                    "name": name,
                    "description": description,
                    "price": price,
                    "currency": "USD",
                    "capacity": capacity,
                    "sales_start_at": utc_at(2026, 7, 1),
                    "sales_end_at": utc_at(2026, 11, 17, 16, 59),
                    "is_active": True,
                },
            )
            ticket_types[code] = ticket_type

        speakers_data = [
            (
                "Dr. Maya Santoso",
                "AI Education Researcher",
                "Indonesia Education Innovation Lab",
                "IDN",
                ["AI in Education", "Learning Analytics", "Responsible AI"],
                True,
            ),
            (
                "Nguyen Minh Quang",
                "Principal Machine Learning Engineer",
                "Vietnam AI Infrastructure Group",
                "VNM",
                ["Generative AI", "Machine Learning", "Cloud Architecture"],
                True,
            ),
            (
                "Sarah Lim",
                "Founder and CEO",
                "LearnAI Labs",
                "SGP",
                ["Education Technology", "Product Strategy", "Startup Development"],
                True,
            ),
            (
                "Arun Prasert",
                "Open-Source AI Advocate",
                "Open Learning Thailand",
                "THA",
                ["Open-Source AI", "Multilingual Models", "Developer Communities"],
                True,
            ),
            (
                "Maria Gabriela Santos",
                "Education Technology Specialist",
                "Philippines Teacher Innovation Network",
                "PHL",
                ["Education Technology", "Teacher Development", "Product Design"],
                True,
            ),
            (
                "Nur Aisyah Rahman",
                "Learning Data Platform Lead",
                "Kuala Lumpur Digital University",
                "MYS",
                ["Educational Data Analytics", "Personalized Learning", "FastAPI"],
                False,
            ),
        ]
        for full_name, title, organization, country, tags, featured in speakers_data:
            await get_or_create(
                session,
                Speaker,
                full_name=full_name,
                defaults={
                    "professional_title": title,
                    "organization_name": organization,
                    "country_code": country,
                    "biography": f"{full_name} shares practical experience building AI solutions for education communities across Southeast Asia.",
                    "profile_photo_url": f"https://ui-avatars.com/api/?name={full_name.replace(' ', '+')}&background=0f766e&color=fff",
                    "linkedin_url": "https://www.linkedin.com/",
                    "expertise_tags": tags,
                    "is_featured": featured,
                    "status": "published",
                },
            )

        sessions_data = [
            ("registration-and-qr-check-in", "Registration and QR Code Check-In", None, "registration", "Main Lobby", 18, 0, 30, 90, 300),
            ("opening-ceremony", "Opening Ceremony", None, "ceremony", "Main Hall", 18, 2, 0, 30, 300),
            ("future-of-ai-in-asean-education", "The Future of AI in ASEAN Education", None, "keynote", "Main Hall", 18, 2, 30, 60, 300),
            ("responsible-ai-for-students-and-teachers", "Building Responsible AI for Students and Teachers", None, "panel", "Main Hall", 18, 3, 45, 75, 300),
            ("designing-ai-architecture-for-education", "Designing AI Architecture for Education", "Track A - AI Learning Assistant", "technical_session", "Main Hall", 18, 6, 0, 60, 300),
            ("building-multilingual-ai-for-asean-learners", "Building Multilingual AI for ASEAN Learners", "Track C - Multilingual Education AI", "technical_session", "Main Hall", 18, 7, 0, 45, 300),
            ("education-challenge-discovery", "Education Challenge Discovery", None, "collaboration", "Innovation Hall", 18, 8, 0, 60, 300),
            ("team-formation-and-project-ideation", "Team Formation and Project Ideation", None, "collaboration", "Innovation Hall", 18, 9, 0, 75, 300),
            ("building-an-ai-education-assistant", "Building an AI Education Assistant", "Track A - AI Learning Assistant", "workshop", "Workshop Room A", 19, 2, 0, 90, 70),
            ("development-sprint-one", "Development Sprint One", None, "sprint", "Workshop Halls", 19, 3, 45, 75, 300),
            ("development-sprint-two", "Development Sprint Two", None, "sprint", "Workshop Halls", 19, 6, 0, 90, 300),
            ("project-demonstration-and-awards", "Project Demonstration, Jury Evaluation, and Awards", None, "demo", "Main Hall", 19, 8, 0, 150, 300),
        ]
        sessions = {}
        for slug, title, track_name, session_type, room, day, hour, minute, duration_minutes, capacity in sessions_data:
            start_at = utc_at(2026, 11, day, hour, minute)
            track_id = tracks[track_name].id if track_name else None
            event_session, _ = await get_or_create(
                session,
                EventSession,
                event_id=event.id,
                slug=slug,
                defaults={
                    "workshop_track_id": track_id,
                    "title": title,
                    "description": f"{title} at ASEAN AI for Education Summit 2026.",
                    "session_type": session_type,
                    "room_name": room,
                    "start_at": start_at,
                    "end_at": start_at + timedelta(minutes=duration_minutes),
                    "capacity": capacity,
                    "status": "scheduled",
                },
            )
            sessions[slug] = event_session

        participants_data = [
            ("rina.prameswari@example.com", "Rina Prameswari", "Jakarta EduTech Studio", "Frontend developer building learning interfaces for Indonesian schools.", "DEVELOPER", RegistrationStatus.CONFIRMED),
            ("thanakorn.s@example.com", "Thanakorn S.", "Bangkok Robotics Classroom", "AI engineer exploring computer vision for classroom attendance.", "PROFESSIONAL", RegistrationStatus.CONFIRMED),
            ("nurul.hakim@example.com", "Nurul Hakim", "KL GovTech Education Lab", "Policy analyst focused on responsible AI and student data protection.", "STUDENT", RegistrationStatus.CONFIRMED),
            ("joel.lim@example.com", "Joel Lim", "Lion City Learning Cloud", "Cloud engineer interested in scalable RAG systems for education.", "DEVELOPER", RegistrationStatus.WAITING_PAYMENT),
            ("camila.reyes@example.com", "Camila Reyes", "Manila AI Guild", "Community organizer supporting teacher productivity tools.", "DEVELOPER", RegistrationStatus.CONFIRMED),
            ("linh.nguyen@example.com", "Linh Nguyen", "Saigon Data Hub", "Data engineer working on school analytics dashboards.", "STUDENT", RegistrationStatus.CANCELED),
            ("aisyah.nordin@example.com", "Aisyah Nordin", "Brunei Digital Office", "Digital transformation specialist for inclusive education programs.", "PROFESSIONAL", RegistrationStatus.CONFIRMED),
            ("sokha.chan@example.com", "Sokha Chan", "Phnom Penh Startup Center", "Startup program lead mentoring multilingual education AI prototypes.", "TEAM", RegistrationStatus.WAITING_PAYMENT),
        ]

        confirmed_tickets = []
        for index, (email, full_name, organization, bio, ticket_code, reg_status) in enumerate(participants_data, start=1):
            user, _ = await get_or_create(
                session,
                User,
                email=email,
                defaults={
                    "password_hash": password,
                    "full_name": full_name,
                    "phone": f"+62812000010{index:02d}",
                    "status": "active",
                    "is_email_verified": index % 2 == 0,
                },
            )
            participant, _ = await get_or_create(
                session,
                ParticipantProfile,
                user_id=user.id,
                defaults={
                    "full_name": full_name,
                    "organization_name": organization,
                    "biography": bio,
                },
            )
            registration_number = f"REG-AIEDU26-{index:04d}"
            confirmed_at = utc_at(2026, 10, 1 + index, 3, 30) if reg_status == RegistrationStatus.CONFIRMED else None
            canceled_at = utc_at(2026, 10, 12, 6, 0) if reg_status == RegistrationStatus.CANCELED else None
            registration, _ = await get_or_create(
                session,
                Registration,
                registration_number=registration_number,
                defaults={
                    "event_id": event.id,
                    "participant_id": participant.id,
                    "ticket_type_id": ticket_types[ticket_code].id,
                    "status": reg_status,
                    "dietary_preference": "Halal meal",
                    "accessibility_requirements": None if index % 3 else "Preferensi kursi dekat aisle.",
                    "emergency_contact_name": f"Emergency Contact {index}",
                    "emergency_contact_phone": f"+62812990010{index:02d}",
                    "consent_snapshot": "participant_directory_consent:v1;privacy_policy:v1;event_terms:v1",
                    "confirmed_at": confirmed_at,
                    "canceled_at": canceled_at,
                },
            )

            ticket_price = ticket_types[ticket_code].price
            order_status = OrderStatus.PAID if reg_status == RegistrationStatus.CONFIRMED else OrderStatus.PENDING
            if reg_status == RegistrationStatus.CANCELED:
                order_status = OrderStatus.CANCELED
            order, _ = await get_or_create(
                session,
                Order,
                order_number=f"ORD-AIEDU26-{index:04d}",
                defaults={
                    "registration_id": registration.id,
                    "subtotal": ticket_price,
                    "discount_amount": 0,
                    "tax_amount": 0,
                    "service_fee": 5,
                    "total_amount": ticket_price + 5,
                    "currency": "USD",
                    "status": order_status,
                    "expires_at": utc_at(2026, 10, 20, 16, 59),
                },
            )
            payment_status = PaymentStatus.SUCCESS if order_status == OrderStatus.PAID else PaymentStatus.PENDING
            if order_status == OrderStatus.CANCELED:
                payment_status = PaymentStatus.FAILED
            await get_or_create(
                session,
                Payment,
                order_id=order.id,
                defaults={
                    "provider": "midtrans",
                    "provider_transaction_id": f"MTX-AIEDU26-{index:04d}",
                    "provider_order_id": order.order_number,
                    "payment_type": "bank_transfer" if index % 2 else "gopay",
                    "gross_amount": order.total_amount,
                    "currency": "USD",
                    "transaction_status": payment_status,
                    "fraud_status": "accept",
                    "raw_response": '{"seed": true}',
                    "paid_at": confirmed_at,
                    "expired_at": order.expires_at,
                },
            )

            if reg_status == RegistrationStatus.CONFIRMED:
                ticket, _ = await get_or_create(
                    session,
                    Ticket,
                    registration_id=registration.id,
                    defaults={
                        "ticket_number": f"TCK-AIEDU26-{index:04d}",
                        "status": TicketStatus.ISSUED,
                    },
                )
                await get_or_create(
                    session,
                    QRToken,
                    ticket_id=ticket.id,
                    defaults={
                        "token_hash": qr_hash(f"TCK-AIEDU26-{index:04d}"),
                        "expires_at": utc_at(2026, 11, 20),
                        "is_active": True,
                    },
                )
                confirmed_tickets.append((ticket, index))

        for ticket, index in confirmed_tickets[:4]:
            await get_or_create(
                session,
                CheckIn,
                ticket_id=ticket.id,
                event_id=event.id,
                defaults={
                    "session_id": sessions["registration-and-qr-check-in"].id if index % 2 else None,
                    "check_in_type": "qr",
                    "check_in_at": utc_at(2026, 11, 18, 0, 35 + index),
                    "check_in_by": admin.id,
                    "gate_name": "JCC Main Gate",
                    "device_id": "seed-device-01",
                    "status": "success",
                    "notes": "Seed demo check-in",
                },
            )

        await session.commit()

    await engine.dispose()
    print("Seed demo data selesai.")
    print("Login demo:")
    print("  admin@aseanaiedu.com / Password123!")
    print("  rina.prameswari@example.com / Password123!")
    print("Event slug: asean-ai-for-education-summit-2026")


if __name__ == "__main__":
    asyncio.run(seed())
