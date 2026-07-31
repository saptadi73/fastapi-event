# Technical Documentation — Backend FastAPI
## ASEAN AI for Education Event Portal

**Version:** 1.0  
**Audience:** Backend Engineering Team  
**Primary Stack:** FastAPI, PostgreSQL 18, SQLAlchemy 2, Alembic, Midtrans, Redis optional  
**Architecture Style:** Modular Monolith with clear bounded modules  
**API Style:** RESTful JSON API  
**Primary Identifier:** UUID

---

# 1. Purpose

This document defines the technical implementation standard for the backend of the ASEAN AI for Education Event Portal.

The backend is responsible for:

- User authentication and authorization
- Participant registration
- Participant profile management
- Ticket management
- Payment processing through Midtrans
- Payment webhook verification
- QR code ticket generation
- Event check-in
- Program and speaker management
- Participant directory and networking
- Email notifications
- Certificate generation
- Administration and reporting
- Audit logging
- Data privacy and consent management

The backend must expose secure REST APIs consumed by the Nuxt frontend.

---

# 2. High-Level Architecture

```text
Nuxt 4 Frontend
        |
        | HTTPS / JSON REST API
        v
Nginx Reverse Proxy
        |
        v
FastAPI Application
        |
        +-- PostgreSQL 18
        +-- Midtrans API
        +-- Email Service
        +-- Object Storage
        +-- QR Code Generator
        +-- Redis / Background Worker (optional)
```

Recommended domains:

```text
https://event.example.com
https://api.event.example.com
```

The frontend must never connect directly to PostgreSQL.

---

# 3. Technology Stack

## Core

- Python 3.12+
- FastAPI
- Uvicorn
- Gunicorn
- PostgreSQL 18
- SQLAlchemy 2.x
- Alembic
- Pydantic 2
- asyncpg
- psycopg2-binary for administrative tooling only
- python-dotenv or pydantic-settings

## Authentication and Security

- python-jose
- passlib
- bcrypt
- cryptography
- email-validator
- python-multipart

## Integrations

- httpx
- Midtrans API
- SMTP or transactional email provider
- qrcode
- Pillow
- Jinja2

## Testing

- pytest
- pytest-asyncio
- pytest-cov
- httpx AsyncClient
- factory-boy optional
- faker optional

## Optional Infrastructure

- Redis
- Celery, Dramatiq, or ARQ
- S3-compatible object storage
- Sentry
- Prometheus and Grafana

---

# 4. Architectural Principles

## 4.1 Modular Monolith

Each business module must be independent and contain its own:

- models
- schemas
- repository
- service
- routes
- constants
- exceptions
- tests

Shared utilities must remain in dedicated core or support packages.

## 4.2 Service Layer

Routes must not contain business logic.

```text
Route
  -> Schema validation
  -> Service
  -> Repository
  -> Database
```

## 4.3 Repository Layer

Database queries must be isolated in repository classes or functions.

## 4.4 Transaction Boundary

A business operation that modifies multiple tables must execute inside one database transaction.

Example:

```text
Confirm Payment
  -> Update payment
  -> Update order
  -> Confirm registration
  -> Generate ticket
  -> Generate QR token
  -> Create audit log
```

All operations must either succeed together or roll back together.

## 4.5 Standard API Response

All endpoints must use a consistent response format.

Success:

```json
{
  "success": true,
  "message": "Registration created successfully",
  "data": {},
  "meta": null,
  "request_id": "uuid"
}
```

Error:

```json
{
  "success": false,
  "message": "Validation failed",
  "errors": [
    {
      "field": "email",
      "code": "INVALID_EMAIL",
      "message": "Email address is invalid"
    }
  ],
  "request_id": "uuid"
}
```

---

# 5. Recommended Project Structure

```text
event-portal-backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── security.py
│   │   ├── logging.py
│   │   ├── exceptions.py
│   │   ├── dependencies.py
│   │   └── constants.py
│   │
│   ├── middleware/
│   │   ├── cors.py
│   │   ├── request_id.py
│   │   ├── audit.py
│   │   ├── timing.py
│   │   └── error_handler.py
│   │
│   ├── support/
│   │   ├── responses.py
│   │   ├── pagination.py
│   │   ├── storage.py
│   │   ├── email.py
│   │   ├── qr.py
│   │   ├── files.py
│   │   └── enums.py
│   │
│   ├── modules/
│   │   ├── identity/
│   │   ├── users/
│   │   ├── participants/
│   │   ├── events/
│   │   ├── speakers/
│   │   ├── sessions/
│   │   ├── workshop_tracks/
│   │   ├── ticket_types/
│   │   ├── registrations/
│   │   ├── orders/
│   │   ├── payments/
│   │   ├── midtrans/
│   │   ├── tickets/
│   │   ├── qr_codes/
│   │   ├── check_ins/
│   │   ├── networking/
│   │   ├── certificates/
│   │   ├── notifications/
│   │   ├── content/
│   │   ├── reports/
│   │   └── audit_logs/
│   │
│   └── api/
│       └── router.py
│
├── alembic/
├── tests/
├── scripts/
├── requirements.txt
├── alembic.ini
├── .env.example
└── README.md
```

Each module:

```text
payments/
├── models.py
├── schemas.py
├── repository.py
├── service.py
├── routes.py
├── constants.py
├── exceptions.py
└── tests/
```

---

# 6. Main Business Modules

## 6.1 Identity

Responsibilities:

- Register account
- Login
- Refresh token
- Logout
- Password reset
- Email verification
- Account activation
- Role assignment

Roles:

```text
participant
speaker
staff
check_in_staff
finance
content_admin
event_admin
super_admin
```

## 6.2 Participants

Responsibilities:

- Participant profile
- Profile visibility
- Skills
- Interests
- Social links
- Directory consent
- Collaboration preferences

## 6.3 Events

Responsibilities:

- Event master data
- Venue
- Start and end date
- Registration period
- Publication status
- Capacity
- Time zone

## 6.4 Speakers

Responsibilities:

- Speaker profile
- Biography
- Professional links
- Expertise
- Featured speaker status
- Speaker publication status

## 6.5 Sessions

Responsibilities:

- Agenda
- Session date and time
- Room
- Session type
- Capacity
- Speaker assignment
- Workshop assignment

## 6.6 Registrations

Responsibilities:

- Participant registration
- Registration status
- Selected ticket
- Selected workshop track
- Consent snapshot
- Dietary and accessibility information

## 6.7 Orders and Payments

Responsibilities:

- Order creation
- Price snapshot
- Promo code
- Payment transaction
- Midtrans integration
- Webhook event storage
- Refund status
- Payment reconciliation

## 6.8 Tickets and QR Codes

Responsibilities:

- Ticket issuance
- Unique QR token
- Ticket status
- Reissue handling
- Ticket revocation

## 6.9 Check-In

Responsibilities:

- QR scanning
- Duplicate check-in detection
- Manual check-in
- Check-in history
- Check-in device or gate
- Attendance reporting

## 6.10 Networking

Responsibilities:

- Participant directory
- Connection requests
- Accepted connections
- Profile bookmarks
- Privacy restrictions

---

# 7. Core Database Design

All primary keys use UUID.

All transactional tables should contain:

```text
id
created_at
updated_at
created_by
updated_by
```

Soft-delete fields where required:

```text
deleted_at
deleted_by
```

## 7.1 users

```text
id UUID PK
email VARCHAR UNIQUE NOT NULL
password_hash TEXT NOT NULL
full_name VARCHAR NOT NULL
phone VARCHAR
status VARCHAR NOT NULL
is_email_verified BOOLEAN
last_login_at TIMESTAMPTZ
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

## 7.2 roles

```text
id UUID PK
code VARCHAR UNIQUE
name VARCHAR
description TEXT
```

## 7.3 user_roles

```text
id UUID PK
user_id UUID FK
role_id UUID FK
UNIQUE(user_id, role_id)
```

## 7.4 participant_profiles

```text
id UUID PK
user_id UUID UNIQUE FK
country_code VARCHAR(3)
city VARCHAR
job_title VARCHAR
organization_name VARCHAR
biography TEXT
profile_photo_url TEXT
linkedin_url TEXT
github_url TEXT
portfolio_url TEXT
years_of_experience INTEGER
profile_completion INTEGER
directory_visible BOOLEAN
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

## 7.5 participant_consents

Stores legal consent history.

```text
id UUID PK
participant_id UUID FK
consent_type VARCHAR
consent_version VARCHAR
consent_text_hash VARCHAR
is_accepted BOOLEAN
accepted_at TIMESTAMPTZ
ip_address INET
user_agent TEXT
```

## 7.6 events

```text
id UUID PK
name VARCHAR
slug VARCHAR UNIQUE
description TEXT
venue_name VARCHAR
venue_address TEXT
timezone VARCHAR
start_at TIMESTAMPTZ
end_at TIMESTAMPTZ
registration_start_at TIMESTAMPTZ
registration_end_at TIMESTAMPTZ
capacity INTEGER
status VARCHAR
published_at TIMESTAMPTZ
```

## 7.7 speakers

```text
id UUID PK
user_id UUID NULL FK
full_name VARCHAR
professional_title VARCHAR
organization_name VARCHAR
country_code VARCHAR(3)
biography TEXT
profile_photo_url TEXT
linkedin_url TEXT
github_url TEXT
website_url TEXT
expertise_tags JSONB
is_featured BOOLEAN
status VARCHAR
```

## 7.8 event_sessions

```text
id UUID PK
event_id UUID FK
workshop_track_id UUID NULL FK
title VARCHAR
slug VARCHAR
description TEXT
session_type VARCHAR
room_name VARCHAR
start_at TIMESTAMPTZ
end_at TIMESTAMPTZ
capacity INTEGER
status VARCHAR
```

## 7.9 speaker_sessions

```text
id UUID PK
speaker_id UUID FK
session_id UUID FK
speaker_role VARCHAR
display_order INTEGER
is_confirmed BOOLEAN
attendance_status VARCHAR
UNIQUE(speaker_id, session_id)
```

## 7.10 ticket_types

```text
id UUID PK
event_id UUID FK
code VARCHAR
name VARCHAR
description TEXT
price NUMERIC(18,2)
currency VARCHAR(3)
capacity INTEGER
sales_start_at TIMESTAMPTZ
sales_end_at TIMESTAMPTZ
is_active BOOLEAN
```

## 7.11 registrations

```text
id UUID PK
event_id UUID FK
participant_id UUID FK
ticket_type_id UUID FK
workshop_track_id UUID NULL FK
registration_number VARCHAR UNIQUE
status VARCHAR
dietary_preference VARCHAR
accessibility_requirements TEXT
emergency_contact_name VARCHAR
emergency_contact_phone VARCHAR
consent_snapshot JSONB
confirmed_at TIMESTAMPTZ
canceled_at TIMESTAMPTZ
```

Recommended statuses:

```text
draft
awaiting_payment
payment_pending
confirmed
canceled
expired
refunded
```

## 7.12 orders

```text
id UUID PK
registration_id UUID FK
order_number VARCHAR UNIQUE
subtotal NUMERIC(18,2)
discount_amount NUMERIC(18,2)
tax_amount NUMERIC(18,2)
service_fee NUMERIC(18,2)
total_amount NUMERIC(18,2)
currency VARCHAR(3)
status VARCHAR
expires_at TIMESTAMPTZ
```

## 7.13 payments

```text
id UUID PK
order_id UUID FK
provider VARCHAR
provider_transaction_id VARCHAR
provider_order_id VARCHAR
payment_type VARCHAR
gross_amount NUMERIC(18,2)
currency VARCHAR(3)
transaction_status VARCHAR
fraud_status VARCHAR
signature_key TEXT
paid_at TIMESTAMPTZ
expired_at TIMESTAMPTZ
raw_response JSONB
```

## 7.14 payment_events

Store every incoming webhook.

```text
id UUID PK
payment_id UUID NULL FK
provider VARCHAR
event_type VARCHAR
provider_event_id VARCHAR
signature_valid BOOLEAN
payload JSONB
received_at TIMESTAMPTZ
processed_at TIMESTAMPTZ
processing_status VARCHAR
processing_error TEXT
```

## 7.15 tickets

```text
id UUID PK
registration_id UUID UNIQUE FK
ticket_number VARCHAR UNIQUE
status VARCHAR
issued_at TIMESTAMPTZ
revoked_at TIMESTAMPTZ
```

## 7.16 qr_tokens

```text
id UUID PK
ticket_id UUID FK
token_hash VARCHAR UNIQUE
expires_at TIMESTAMPTZ NULL
is_active BOOLEAN
generated_at TIMESTAMPTZ
```

Do not store only plain predictable registration IDs in QR codes.

## 7.17 check_ins

```text
id UUID PK
ticket_id UUID FK
event_id UUID FK
session_id UUID NULL FK
check_in_type VARCHAR
check_in_at TIMESTAMPTZ
check_in_by UUID FK
gate_name VARCHAR
device_id VARCHAR
status VARCHAR
notes TEXT
```

---

# 8. Registration and Payment Workflow

```text
1. User creates account
2. User verifies email
3. User completes participant profile
4. User accepts privacy and directory consent
5. User selects ticket and workshop track
6. Backend validates ticket availability
7. Backend creates registration in awaiting_payment status
8. Backend creates order
9. Backend requests Midtrans transaction token
10. Frontend opens Midtrans Snap
11. Midtrans processes payment
12. Midtrans sends webhook to backend
13. Backend verifies webhook signature
14. Backend stores payment event
15. Backend updates payment and order status
16. Backend confirms registration
17. Backend generates ticket and QR token
18. Backend sends confirmation email
```

The browser callback is never the source of truth for payment confirmation.

---

# 9. Midtrans Integration Standard

## 9.1 Transaction Creation

Backend endpoint:

```http
POST /api/v1/payments/midtrans/create
```

Request:

```json
{
  "registration_id": "uuid"
}
```

Backend must:

- Validate registration ownership
- Validate order amount from database
- Never trust amount sent by frontend
- Create Midtrans request
- Store provider order ID
- Return Snap token and redirect URL

Response:

```json
{
  "success": true,
  "data": {
    "snap_token": "token",
    "redirect_url": "https://app.midtrans.com/snap/v4/redirection/..."
  }
}
```

## 9.2 Webhook

```http
POST /api/v1/webhooks/midtrans
```

Validation:

- Verify signature key
- Validate order ID
- Validate gross amount
- Apply idempotency
- Store raw payload
- Log processing result

## 9.3 Idempotency

Repeated webhook notifications must not create duplicate tickets or duplicate payment records.

Use:

```text
provider_event_id
provider_transaction_id
provider_order_id
```

with unique constraints where appropriate.

---

# 10. API Endpoint Standards

Base URL:

```text
/api/v1
```

## Authentication

```text
GET /auth/me
PUT /auth/me
POST /auth/forgot-password
POST /auth/reset-password
POST /auth/verify-email
POST /auth/register
POST /auth/login
POST /auth/refresh
POST /auth/logout
PUT /auth/password
```

### Authentication endpoint payload and response

Base response format:

```json
{
  "success": true,
  "message": "string",
  "data": {},
  "request_id": "string",
  "timestamp": "2026-01-01T00:00:00Z"
}
```

`GET /api/v1/auth/me`

Request:

```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

Response:

```json
{
  "success": true,
  "message": "Data profil berhasil diambil",
  "data": {
    "user": {
      "id": "uuid",
      "email": "user@example.com",
      "full_name": "Nama Pengguna",
      "status": "active",
      "is_email_verified": true,
      "created_at": "2026-01-01T00:00:00Z"
    }
  }
}
```

`PUT /api/v1/auth/me`

Request:

```json
{
  "full_name": "Nama Baru",
  "phone": "0812xxxx"
}
```

Response:

```json
{
  "success": true,
  "message": "Profil berhasil diperbarui",
  "data": {
    "user": {
      "id": "uuid",
      "email": "user@example.com",
      "full_name": "Nama Baru",
      "status": "active",
      "is_email_verified": true,
      "created_at": "2026-01-01T00:00:00Z"
    }
  }
}
```

`PUT /api/v1/auth/password`

Request:

```json
{
  "current_password": "lama1234",
  "new_password": "baru12345",
  "confirm_password": "baru12345"
}
```

Response:

```json
{
  "success": true,
  "message": "Password berhasil diubah",
  "data": {
    "changed": true
  }
}
```

Error common:

```json
{
  "success": false,
  "message": "Password saat ini tidak sesuai",
  "data": null,
  "code": "INVALID_CREDENTIAL"
}
```

```json
{
  "success": false,
  "message": "Konfirmasi password tidak cocok",
  "data": null,
  "code": "PASSWORD_MISMATCH"
}
```

`POST /api/v1/auth/forgot-password`

Request:

```json
{
  "email": "user@example.com"
}
```

Response:

```json
{
  "success": true,
  "message": "Instruksi reset password telah dikirim",
  "data": {
    "email": "user@example.com",
    "reset_token": "jwt-reset-token-for-dev"
  }
}
```

`POST /api/v1/auth/reset-password`

Request:

```json
{
  "token": "jwt-reset-token",
  "password": "baru12345",
  "confirm_password": "baru12345"
}
```

Response:

```json
{
  "success": true,
  "message": "Password berhasil diubah",
  "data": {
    "token": "jwt-reset-token"
  }
}
```

`POST /api/v1/auth/verify-email`

Request:

```json
{
  "token": "jwt-email-verification-token"
}
```

Response:

```json
{
  "success": true,
  "message": "Email berhasil diverifikasi",
  "data": {
    "token": "jwt-email-verification-token"
  }
}
```

## Public Event Content

```text
GET /events/{slug}
GET /events/{slug}/sessions
GET /events/{slug}/speakers
GET /events/{slug}/ticket-types
GET /events/{slug}/workshop-tracks
```

## Participant

```text
GET /participants/me
PUT /participants/me
PUT /participants/me/privacy
GET /participants
GET /participants/{id}
POST /participants/{id}/connections
```

## Registration

```text
POST /registrations
GET /registrations/me
GET /registrations/{id}
PUT /registrations/{id}
POST /registrations/{id}/cancel
```

## Payments

```text
POST /payments/midtrans/create
GET /payments/{id}
GET /orders/{id}
POST /webhooks/midtrans
```

## Tickets

```text
GET /tickets/me
GET /tickets/{id}/qr
POST /tickets/{id}/reissue
```

## Check-In

```text
POST /check-ins/scan
POST /check-ins/manual
GET /check-ins
```

## Admin

```text
GET /admin/dashboard
GET /admin/registrations
GET /admin/payments
GET /admin/check-ins
POST /admin/speakers
PUT /admin/speakers/{id}
POST /admin/sessions
PUT /admin/sessions/{id}
```

---

# 11. Authentication and Authorization

Recommended token strategy:

```text
Access token:
- Short lifetime
- Returned to frontend memory

Refresh token:
- HttpOnly
- Secure
- SameSite=Lax
- Rotated on refresh
```

Do not store refresh tokens in localStorage.

Authorization must be enforced in backend dependencies.

Example:

```python
@router.get("/admin/registrations")
async def list_registrations(
    current_user: User = Depends(require_roles("event_admin", "super_admin"))
):
    ...
```

---

# 12. Security Requirements

Mandatory:

- HTTPS only
- Password hashing using bcrypt
- JWT expiration
- Refresh token rotation
- Rate limiting
- CORS allow-list
- Request ID
- Input validation
- File type and file size validation
- SQL injection protection through SQLAlchemy
- Midtrans signature validation
- Audit logs for administrative actions
- Secure cookies
- CSRF protection when cookie-based authentication is used
- No payment card storage
- No sensitive data in application logs

Recommended headers:

```text
Strict-Transport-Security
X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Content-Security-Policy
```

---

# 13. File Storage

Store only file metadata in PostgreSQL.

File types:

- Profile photos
- Speaker photos
- Event banners
- Sponsor logos
- Presentation materials
- Certificates
- Invoices

Recommended approach:

```text
PostgreSQL:
- file ID
- original name
- object key
- MIME type
- size
- checksum
- owner
- visibility

Object Storage:
- actual file binary
```

---

# 14. Background Jobs

Recommended asynchronous jobs:

- Send confirmation email
- Send payment reminder
- Generate invoice PDF
- Generate certificate
- Send event reminder
- Process bulk email
- Export reports
- Generate image thumbnails

Payment confirmation database updates should remain synchronous and transactional.

---

# 15. Logging and Audit

Application logs must include:

```text
timestamp
level
request_id
user_id
route
HTTP method
status code
duration
error code
```

Audit logs must include:

```text
actor_user_id
action
resource_type
resource_id
old_value
new_value
ip_address
user_agent
created_at
```

Audit examples:

- Ticket price changed
- Registration canceled
- Payment manually reconciled
- QR ticket reissued
- Participant profile hidden
- Admin role assigned

---

# 16. Testing Strategy

## Unit Tests

- Service logic
- Price calculation
- Consent validation
- Ticket availability
- QR token validation
- Payment status mapping

## Integration Tests

- Registration creation
- Order creation
- Midtrans webhook
- Ticket issuance
- Check-in
- Role authorization

## End-to-End API Tests

```text
Register
-> Complete profile
-> Create registration
-> Create payment
-> Simulate webhook
-> Confirm ticket
-> Scan QR
```

Minimum target:

```text
Core business modules: 80% coverage
Payment and ticket modules: 90% coverage
```

---

# 17. Database Migration Standard

Use Alembic for all schema changes.

Rules:

- Never modify production schema manually
- One migration per logical change
- Migration must contain upgrade and downgrade
- Use explicit constraint names
- Review generated migrations
- Test migration on staging database
- Back up production database before release

Naming example:

```text
20260730_001_create_event_registration_tables.py
```

---

# 18. Environment Configuration

Example `.env.example`:

```env
APP_NAME=ASEAN AI Event Portal
APP_ENV=development
APP_DEBUG=true
API_PREFIX=/api/v1

DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/event_portal

JWT_SECRET_KEY=change-me
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000

MIDTRANS_SERVER_KEY=
MIDTRANS_CLIENT_KEY=
MIDTRANS_IS_PRODUCTION=false

SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
EMAIL_FROM=

STORAGE_ENDPOINT=
STORAGE_BUCKET=
STORAGE_ACCESS_KEY=
STORAGE_SECRET_KEY=
```

Never commit real `.env` files.

---

# 19. Deployment

Recommended production process:

```text
Nginx
  -> Gunicorn
      -> Uvicorn Workers
          -> FastAPI
              -> PostgreSQL
```

Example systemd execution:

```bash
gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  --bind 127.0.0.1:8007 \
  --workers 4 \
  --timeout 120
```

Deployment checklist:

- Run tests
- Run Alembic migration
- Restart backend service
- Verify health endpoint
- Verify Midtrans webhook
- Verify email service
- Verify QR generation
- Verify CORS
- Verify logs

Health endpoints:

```text
GET /health
GET /health/database
GET /health/readiness
```

---

# 20. Backend Definition of Done

A backend feature is complete when:

- Database migration exists
- Model is implemented
- Schema validation exists
- Repository is implemented
- Service logic is implemented
- Route is documented
- Authorization is enforced
- Audit requirement is reviewed
- Unit and integration tests pass
- API response follows standard format
- OpenAPI documentation is updated
- Error cases are handled
- No secrets are committed
