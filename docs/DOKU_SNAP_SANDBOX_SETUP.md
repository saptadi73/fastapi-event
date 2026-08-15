# DOKU SNAP Sandbox Setup — IWBIF 2026

## Endpoint publik

- Token URL pada **Integration → API Keys**:
  `https://<backend-domain>/api/v1/doku/snap/authorization/v1/access-token/b2b`
- Notification URL pada setiap **Virtual Account SNAP → Configure**:
  `https://<backend-domain>/api/v1/webhooks/doku/snap/va/payment`

Endpoint callback tidak memakai JWT user. Keamanan menggunakan RSA token request,
Bearer token merchant, HMAC-SHA512, validasi timestamp dan nominal, serta
idempotensi `X-EXTERNAL-ID`.

## API keys dan RSA

Jalankan sekali:

```powershell
.\.venv\Scripts\python.exe scripts\generate_doku_snap_keys.py
```

Unggah `.secrets/doku-snap-public.pem` ke DOKU. Jangan mengunggah atau membagikan
`.secrets/doku-snap-private.pem`.

## Environment backend

```env
DOKU_BASE_URL=https://api-sandbox.doku.com
DOKU_SNAP_PARTNER_ID=<Client ID merchant dari DOKU>
DOKU_SNAP_CLIENT_SECRET=<Secret Key dari DOKU>
DOKU_SNAP_PRIVATE_KEY_PATH=.secrets/doku-snap-private.pem
DOKU_SNAP_DOKU_PUBLIC_KEY_PATH=.secrets/doku-snap-doku-public.pem
DOKU_SNAP_DOKU_CLIENT_ID=<X-CLIENT-KEY/X-PARTNER-ID milik DOKU untuk callback>
DOKU_SNAP_VA_CHANNELS_JSON={"BCA":{"partner_service_id":"<BIN BCA>"},"BNI":{"partner_service_id":"<BIN BNI>"},"BNC":{"partner_service_id":"<BIN BNC>"}}
```

Public key dan Client ID callback DOKU diperoleh dari DOKU/onboarding. Nilai
`partner_service_id` adalah BIN per channel dan harus disimpan sebagai string.

## Harga IDR

Set `payment_amount_idr` melalui CRUD admin delegate package. `currency` dan
`amount` tetap menjadi harga display; charge DOKU memakai nilai IDR tersebut.

## Urutan uji sandbox

1. Pastikan migrasi `202608150014` aktif.
2. Upload public key merchant dan daftarkan Token URL.
3. Configure BIN serta Notification URL setiap bank.
4. Set `payment_amount_idr` paket.
5. Login peserta dan panggil `POST /api/v1/payments/doku/direct/va`.
6. Tampilkan `virtual_account_no` dan `instructions_url` di frontend.
7. Simulasikan pembayaran melalui DOKU sandbox.
8. Pastikan payment menjadi `success` dan order/registration menjadi `paid`.
