# Registration Email Notifications

Backend mengirim email konfirmasi setelah `POST /api/v1/auth/register` berhasil.
Email dikirim sebagai background task sehingga respons registrasi tidak tertahan
oleh koneksi SMTP.

Isi email:

- Konfirmasi akun berhasil terdaftar pada event IWBIF 2026.
- Link `FRONTEND_LOGIN_URL` untuk login dan melanjutkan pendaftaran.
- Sender: `info@iwbif.id`.

## Titan Email SMTP

Konfigurasi berada di `.env` dan jangan dikirim ke frontend:

```env
EMAIL_ENABLED=true
EMAIL_SMTP_HOST=smtp.titan.email
EMAIL_SMTP_PORT=465
EMAIL_SMTP_USE_SSL=true
EMAIL_SMTP_USE_TLS=false
EMAIL_SMTP_USERNAME=info@iwbif.id
EMAIL_SMTP_PASSWORD=<Titan-Mailbox-or-App-Password>
EMAIL_FROM_ADDRESS=info@iwbif.id
EMAIL_FROM_NAME=IWBIF 2026
FRONTEND_LOGIN_URL=https://frontend.example.com/login
```

`EMAIL_SMTP_PASSWORD` harus diisi dengan password mailbox Titan. Jika 2FA aktif,
gunakan application password Titan. Akses aplikasi pihak ketiga juga harus aktif
pada akun Titan. Jangan menyimpan password di source control.

Konfigurasi utama Titan menggunakan SSL/TLS langsung pada port 465. Alternatif
STARTTLS port 587 dapat digunakan dengan `EMAIL_SMTP_USE_SSL=false` dan
`EMAIL_SMTP_USE_TLS=true` jika port 465 diblokir oleh jaringan server.

Untuk development, gunakan `EMAIL_ENABLED=false`. Untuk production, isi secret
password melalui secret manager atau environment deployment lalu restart backend.

Jika SMTP gagal, akun tetap tersimpan dan backend mencatat error tanpa
mengembalikan password atau credential ke response API.
