# DOKU Production Smoke Test Script

Berikut script untuk melakukan pemeriksaan cepat integrasi pembayaran DOKU di backend production:

- Lokasi script: `scripts/doku_smoke_test.py`
- Output: file JSON detail di folder `reports/` (contoh `doku_smoke_report_YYYYMMDD_HHMMSS.json`)

## Cara pakai

```bash
python scripts/doku_smoke_test.py \
  --base-url https://api-event.gagakrimang.web.id \
  --email peserta.or.admin@email \
  --password "********" \
  --registration-id <REGISTRATION_UUID> \
  --bank-code MANDIRI \
  --run-webhook \
  --output-dir reports
```

Parameter penting:

- `--base-url`: domain backend aktif.
- `--email`, `--password`: akun untuk login ke API.
- `--registration-id` (opsional): jika tidak diisi, script ambil invoice pertama dari `/api/v1/payments/me/invoices`.
- `--bank-code`: kode bank VA yang valid dari metode yang aktif (`MANDIRI`, `BCA`, `BNI`, `BRI`).
- `--run-webhook`: aktifkan simulasi callback DOKU (legacy + SNAP).
- `--skip-legacy-webhook`: lewati simulasi `POST /api/v1/webhooks/doku`.
- `--skip-snap-webhook`: lewati simulasi `POST /api/v1/webhooks/doku/snap/va/payment`.
- `--mode`: salah satu dari:
  - `full` (default): payment + legacy webhook + SNAP webhook
  - `payment-only`: hanya sampai create VA, tanpa webhook
  - `snap-only`: payment + SNAP webhook
  - `legacy-only`: payment + legacy webhook
- `--dry-run`: hanya cek login, metode, dan pemilihan registrasi (tanpa membuat transaksi).
- `--output-dir`: lokasi file report.
- `--assert-on-failure`: exit code non-zero jika hasil gagal (dan mengecek required-step jika diset).
- `--required-steps`: list step wajib, contoh `login,doku_direct_methods,create_doku_direct_va`.
- `--assert-payment-status`: validasi status akhir transaksi; bisa 1 atau lebih nilai dipisah dengan koma atau `|` (contoh `SUCCESS|PAID` atau `PENDING,SUCCESS`) dan exit non-zero jika tidak match.

## Environment variable (untuk simulasi webhook)

Atur env pada server tempat script dijalankan:

- `DOKU_CLIENT_ID`
- `DOKU_SECRET_KEY`
- `DOKU_SNAP_CLIENT_SECRET`
- `DOKU_SNAP_PARTNER_ID`
- `DOKU_SNAP_DOKU_CLIENT_ID` (kalau backend menggunakannya)
- `DOKU_SNAP_VA_NOTIFICATION_PATH` (opsional, default `/api/v1/webhooks/doku/snap/va/payment`)
- `DOKU_SNAP_MOCK_TOKEN` *(opsional, untuk simulasi SNAP webhook)*
- `DOKU_SNAP_PRIVATE_KEY_PATH` *(wajib jika ingin auto-generate token SNAP; default mengarah ke private key merchant)*

Catatan:

- Legacy webhook DOKU bisa disimulasikan penuh selama `DOKU_CLIENT_ID` dan `DOKU_SECRET_KEY` tersedia.
- SNAP webhook memerlukan token notifikasi B2B valid. Jika `DOKU_SNAP_MOCK_TOKEN` tidak diset, script akan mencoba generate otomatis memakai `DOKU_SNAP_PARTNER_ID` + `DOKU_SNAP_PRIVATE_KEY_PATH`.
- Jika auto-generate gagal, skrip tetap menyimpan log kegagalan di step `simulate_snap_webhook` dan melanjutkan.

## Flow yang dijalankan script

1. Login ke `/auth/login`.
2. Cek metode VA dari `/api/v1/payments/doku/direct/methods`.
3. Pilih `registration_id` dari argumen atau dari invoice user.
4. Buat VA via `POST /api/v1/payments/doku/direct/va`.
5. Ambil ulang payment dan order untuk verifikasi.
6. Jika `--run-webhook`, kirim simulasi callback ke:
   - `POST /api/v1/webhooks/doku`
   - `POST /api/v1/webhooks/doku/snap/va/payment` (jika token mock tersedia)

## Contoh output report

Report berisi:

- Metadata eksekusi
- Step-by-step hasil tiap tahap (`ok`/`false`)
- Objek hasil akhir `summary` dengan `user`, `payment`, `order`, dan error bila terjadi kegagalan.
