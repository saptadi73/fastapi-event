# IWBIF 2026 Event Portal — FastAPI Backend

Backend modular untuk International Women Business & Investment Forum 2026.
Domain utama mencakup delegate registration, package dan payment, travel dan
accommodation, exhibitor showcase, participant directory, business matching,
messaging, meeting scheduling, organizer-assisted matching dengan mutual consent,
operational reporting, ticket/QR, check-in, dan notification.

## Quick start

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\seed_iwbif_2026.py
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

Seed bersifat idempotent dan membuat event IWBIF 2026, paket delegate,
aktivitas event, serta slot business matching. API tersedia pada `/api/v1`
dan dokumentasi interaktif pada `/docs`.

Business matching mendukung dua jalur: request langsung antar-participant dan
usulan organizer. Usulan organizer membutuhkan respons kedua pihak, dapat
dikonversi otomatis menjadi meeting scheduling, dan dikelola melalui dashboard
report/settings tanpa membuka conversation privat.

Dokumen acuan:

- `docs/IWAPI_SUMMIT_WEBSITE.md`
- `docs/IWBIF_2026_Backend_Implementation_Reference.md`
- `docs/Backend_Business_Matching_FastAPI_v2.md`
- `docs/FRONTEND_DOKU_PAYMENT_INTEGRATION.md`
- `docs/FRONTEND_IWBIF_REGISTRATION_FLOW.md`
- `docs/FRONTEND_BUSINESS_MATCHING_MESSAGING.md`
