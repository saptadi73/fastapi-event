# BRI Non-SNAP Inquiry

Setelah backend versi ini di-deploy, isi dashboard production:

- Inquiry URL: `https://api.iwbif.id/api/v1/doku/va/inquiry`
- Payment Notification URL: `https://api.iwbif.id/api/v1/webhooks/doku`

Endpoint inquiry menerima POST dengan Client-Id, Request-Id,
Request-Timestamp, dan Signature HMACSHA256 Non-SNAP. Gunakan
DOKU_CLIENT_ID dan DOKU_SECRET_KEY production di backend. Timestamp UTC
ditoleransi hingga 5 menit. Tidak menggunakan JWT peserta atau token SNAP.
Response bisnis ditandatangani dengan Response-Timestamp dan digest body
response; tidak dibungkus format response umum aplikasi.

## Cakupan

BRI Non-SNAP FIX_BILL. Pencarian harus cocok persis dengan payment provider
`doku`, channel `BRI` atau `VIRTUAL_ACCOUNT_BRI`, dan virtual_account_no.
Payment harus mempunyai provider_order_id, nominal bulat IDR, serta order
dan pemilik yang valid. Inquiry hanya membaca data, tidak melunasi transaksi.
Nominal berasal dari payment terkait (termasuk bagian pembayaran), bukan
total parent order. VA tidak dikenal mengembalikan HTTP 404 billing_not_found;
lunas, kedaluwarsa, dan penolakan mengembalikan HTTP 400 sesuai dokumentasi.
Request autentikasi tidak valid ditolak sebelum pencarian database.

Endpoint ini tidak menerbitkan nomor VA DIPC atau mengubah Checkout menjadi
DIPC. Checkout belum tentu menyimpan nomor VA sebelum notifikasi; VA tanpa
mapping lokal tidak akan dianggap valid. Untuk menggunakan DIPC sungguhan,
alur penerbitan VA dan penyimpanan mapping invoice harus diintegrasikan dan
diuji bersama DOKU terlebih dahulu. Jangan mengisi mapping dengan tebakan
dari suffix nomor VA. Kanal SNAP tetap memakai protokol/endpoint terpisah.

## Verifikasi deployment

1. Deploy kode dan restart backend; periksa route POST di OpenAPI.
2. Daftarkan Inquiry URL dan Notification URL di atas.
3. Uji inquiry bertanda tangan dari DOKU; VA asing harus menghasilkan 404,
   bukan 200 sukses palsu. GET dari browser bukan pengujian inquiry.
4. Jika memakai DIPC, uji VA terdaftar, lunas, kedaluwarsa, dan notification
   pembayaran end-to-end sebelum membukanya untuk peserta.

## Sumber resmi

- https://jokul.doku.com/docs/docs/jokul-direct/virtual-account/bri-va-guide/
- https://developers.doku.com/get-started-with-doku-api/signature-component/non-snap/signature-component-from-request-header
- https://developers.doku.com/get-started-with-doku-api/signature-component/non-snap/signature-componen-from-response-header

Dokumentasi BRI Non-SNAP berasal dari portal legacy DOKU. Kontrak ini tidak
boleh disamakan dengan format inquiry BRI SNAP v1.1.
