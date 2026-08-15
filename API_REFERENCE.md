# IWBIF 2026 API Reference

## DOKU Direct API SNAP

- `GET /api/v1/payments/doku/direct/methods` — daftar bank VA terkonfigurasi.
- `POST /api/v1/payments/doku/direct/va` — membuat VA Close Amount (JWT user wajib).
- `GET /api/v1/payments/{payment_id}` — membaca status pembayaran.
- `POST /api/v1/doku/snap/authorization/v1/access-token/b2b` — Token URL untuk callback DOKU.
- `POST /api/v1/webhooks/doku/snap/va/payment` — Notification URL VA SNAP.

Payload pembuatan VA: `{"registration_id":"UUID","bank_code":"BCA"}`.
Nominal selalu berasal dari `delegate_packages.payment_amount_idr`; frontend tidak
boleh mengirim atau menghitung nominal pembayaran.

OpenAPI merupakan referensi endpoint yang kanonik dan dapat dibuka melalui
`GET /openapi.json` atau antarmuka `/docs`.

Kelompok endpoint utama:

- `/api/v1/events` — event, program, dan speaker.
- `POST /api/v1/events/{event_id}/registrations` — registrasi delegate IWBIF.
- `GET /api/v1/events/{event_id}/delegate-packages` — paket delegate.
- `GET /api/v1/events/{event_id}/activities` — pilihan aktivitas.
- `GET /api/v1/events/{event_id}/business-matching-slots` — slot matching.
- `GET|POST /api/v1/events/{event_id}/exhibitors` — exhibitor/SME showcase.
- `GET|POST /api/v1/registrations/{registration_id}/documents` — dokumen privat.
- `GET|POST|PATCH|DELETE /api/v1/registrations/{registration_id}/business-matching-profile` — profil bisnis delegate confirmed.
- `GET /api/v1/events/{event_id}/business-matching/participants` — discovery.
- `GET /api/v1/events/{event_id}/business-matching/recommendations` — recommendation.
- `GET|POST /api/v1/events/{event_id}/meetings` — permintaan dan jadwal meeting.
- `GET|POST /api/v1/events/{event_id}/conversations` — conversation dalam event.
- `GET /api/v1/conversations/{conversation_id}/messages` — pesan conversation.
- `POST /api/v1/conversations/{conversation_id}/messages` — kirim pesan/reply.
- `PATCH|DELETE /api/v1/conversations/{conversation_id}/messages/{message_id}` — edit/soft-delete pesan sendiri.
- `POST /api/v1/conversations/{conversation_id}/read` — read receipt.
- `GET /api/v1/messages/unread-count` — badge unread message.
- `WS /api/v1/ws/conversations/{conversation_id}?token=<JWT>` — event messaging realtime.
- `GET /api/v1/notifications` — notification center.
- `POST /api/v1/payments/doku/checkout` — membuat DOKU Checkout.
- `POST /api/v1/webhooks/doku` — notifikasi pembayaran DOKU terverifikasi.
- `GET /api/v1/tickets/me` — tiket milik participant.
- `GET /api/v1/check-ins` — daftar check-in.
- `/api/v1/admin/*` — operasi organizer yang dilindungi role.

Seluruh identifier resource menggunakan UUID. Response mengikuti envelope
`success`, `message`, `data`, `meta`, `request_id`, dan `timestamp`.

Kontrak penggunaan DOKU dari aplikasi frontend, termasuk request/response,
redirect, callback, polling status, error handling, dan TypeScript interface,
tersedia di `docs/FRONTEND_DOKU_PAYMENT_INTEGRATION.md`.
