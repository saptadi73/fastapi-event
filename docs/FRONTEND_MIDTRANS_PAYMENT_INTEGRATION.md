# Integrasi Frontend Midtrans Snap

Backend menjadi pemilik Server Key, nominal, pembuatan transaksi, dan verifikasi
notification. Frontend tidak boleh menyimpan atau mengirim Server Key.

## Memilih gateway

Frontend dapat menampilkan metode aktif dari `GET /api/v1/payments/methods` lalu
memanggil salah satu endpoint berikut dengan access token pengguna:

- DOKU: `POST /api/v1/payments/doku/checkout`
- Midtrans: `POST /api/v1/payments/midtrans/checkout`

Body keduanya sama dan harus memuat tepat satu sumber pembayaran:

```json
{"order_id":"<uuid>"}
```

atau:

```json
{"registration_id":"<uuid>"}
```

Response Midtrans berisi `payment_url`, `token`, `payment_id`, dan
`requires_payment`. Implementasi paling sederhana adalah redirect browser ke
`payment_url`. Bila memakai Snap.js, `token` boleh diberikan ke `snap.pay()`;
Client Key Midtrans adalah public credential, tetapi Server Key tetap hanya di
backend.

Redirect browser bukan bukti pembayaran. Setelah pengguna kembali, frontend
harus membaca `GET /api/v1/payments/{payment_id}` sampai status final. Backend
hanya mengubah pembayaran menjadi sukses setelah signature notification valid
dan status tersebut dikonfirmasi lagi melalui API Midtrans.

## Konfigurasi Midtrans

Atur Payment Notification URL di dashboard Midtrans ke:

`https://<backend-public-host>/api/v1/webhooks/midtrans`

Gunakan sandbox lebih dahulu dengan `MIDTRANS_IS_PRODUCTION=false`. Setelah uji
berhasil, pasang production Server/Client Key dan ubah flag menjadi `true`.

Laporan admin sengaja dipisahkan:

- DOKU: `/api/v1/admin/reports/payments` dan `.csv`
- Midtrans: `/api/v1/admin/reports/payments/midtrans` dan `.csv`
