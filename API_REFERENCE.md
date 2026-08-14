# IWBIF 2026 API Reference

OpenAPI merupakan referensi endpoint yang kanonik dan dapat dibuka melalui
`GET /openapi.json` atau antarmuka `/docs`.

Kelompok endpoint utama:

- `/api/v1/events` — event, program, dan speaker.
- `/api/v1/events/{event_id}/registrations` — registrasi delegate IWBIF.
- `/api/v1/events/{event_id}/delegate-packages` — paket delegate.
- `/api/v1/events/{event_id}/activities` — pilihan aktivitas.
- `/api/v1/events/{event_id}/exhibitors` — exhibitor/SME showcase.
- `/api/v1/registrations/{registration_id}/documents` — dokumen privat.
- `/api/v1/registrations/{registration_id}/business-matching-profile` — profil bisnis delegate confirmed.
- `/api/v1/events/{event_id}/business-matching/*` — discovery dan recommendation.
- `/api/v1/events/{event_id}/meetings` — permintaan dan jadwal meeting.
- `/api/v1/conversations` dan `/api/v1/notifications` — komunikasi.
- `/api/v1/payments`, `/api/v1/tickets`, dan `/api/v1/check-ins` — pembayaran dan akses acara.
- `/api/v1/admin/*` — operasi organizer yang dilindungi role.

Seluruh identifier resource menggunakan UUID. Response mengikuti envelope
`success`, `message`, `data`, `meta`, `request_id`, dan `timestamp`.
