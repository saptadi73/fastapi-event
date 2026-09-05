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

Operasional pembayaran menyediakan daftar transaksi terpadu untuk seluruh
provider melalui `GET /api/v1/admin/transactions`. Role `admin` dan `organizer`
dapat merekonsiliasi transaksi manual maupun payment gateway melalui
`PATCH /api/v1/admin/transactions/{payment_id}/status`, atau menghapus transaksi
yang tidak lagi diperlukan melalui `DELETE /api/v1/admin/transactions/{payment_id}`.
Delete pembayaran bersifat soft-delete dan mempertahankan audit. Operasi massal
tersedia melalui `POST /api/v1/admin/transactions/bulk-actions`.
Setiap transaksi mengirim `allowed_actions`, sehingga frontend tidak perlu
menduplikasi aturan transisi status.

Checkout package bersifat resumable. Item cart menjadi snapshot pending order
yang dapat ditemukan melalui `GET /api/v1/orders`, dilanjutkan melalui
`POST /api/v1/orders/{order_id}/continue-payment`, atau dibatalkan secara
soft-cancel melalui `DELETE /api/v1/orders/{order_id}` tanpa menghapus riwayat
payment attempt.
Kontrak lengkap tersedia di `docs/API_REFERENCE.md`.

Form exhibitor menggunakan **Booth number requested** dengan pilihan 1–40.
Field API tetap `booth_size_requested` dan berisi nomor sebagai string.
User yang sudah memiliki registrasi exhibitor atau order exhibitor aktif,
termasuk pending, harus melanjutkan profil/pembayaran yang sudah ada.
Tambah cart dan checkout memblokir pembelian ulang. Kontrak pengecekan status
dan alur frontend tersedia di [Frontend Store Purchase Flow](docs/FRONTEND_STORE_PURCHASE_FLOW.md#periksa-pembelian-exhibitor)
dan [API Reference](docs/API_REFERENCE.md#8-exhibitor).

Backend mendukung locale `en` dan `zh-CN` (Simplified Chinese) tanpa
menggandakan endpoint. Frontend dapat memakai `?locale=zh-CN` atau header
`Accept-Language: zh-CN`. Preferensi email disimpan pada `preferred_locale` user.
Status, error code, provider, dan `allowed_actions` tetap canonical.
Konten dinamis dikelola melalui `/api/v1/admin/content-translations`, dengan
fallback locale yang eksplisit dan snapshot nama produk pada saat checkout.

Dokumen acuan:

- `docs/BILINGUAL_BACKEND_TODO.md` — checklist implementasi dan acceptance bilingual.
- `docs/FRONTEND_BILINGUAL_CONTENT_INTEGRATION.md` — kontrak frontend editor speaker dan agenda bilingual.
- `docs/I18N_MESSAGE_AUDIT.md` — inventarisasi dan kebijakan fallback pesan API.
- `docs/IWAPI_SUMMIT_WEBSITE.md`
- `docs/IWBIF_2026_Backend_Implementation_Reference.md`
- `docs/Backend_Business_Matching_FastAPI_v2.md`
- `docs/FRONTEND_DOKU_PAYMENT_INTEGRATION.md`
- `docs/FRONTEND_IWBIF_REGISTRATION_FLOW.md`
- `docs/FRONTEND_BUSINESS_MATCHING_MESSAGING.md`
