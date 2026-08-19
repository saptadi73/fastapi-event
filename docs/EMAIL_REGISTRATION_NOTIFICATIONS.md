# Registration Email Notifications

Backend mengirim email konfirmasi setelah `POST /api/v1/auth/register` berhasil.
Email dikirim sebagai background task sehingga respons registrasi tidak tertahan
oleh koneksi SMTP.

Isi email:

- Konfirmasi akun berhasil terdaftar pada event IWBIF 2026.
- Link `FRONTEND_LOGIN_URL` untuk login dan melanjutkan pendaftaran.
- Sender: `events@kupu-gsc.co.id`.

## Google Workspace SMTP

Konfigurasi berada di `.env` dan jangan dikirim ke frontend:

```env
EMAIL_ENABLED=true
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USE_TLS=true
EMAIL_SMTP_USERNAME=events@kupu-gsc.co.id
EMAIL_SMTP_PASSWORD=<Google-Workspace-App-Password>
EMAIL_FROM_ADDRESS=events@kupu-gsc.co.id
EMAIL_FROM_NAME=IWBIF 2026
FRONTEND_LOGIN_URL=https://frontend.example.com/login
```

`EMAIL_SMTP_PASSWORD` harus diisi dengan credential SMTP/App Password yang
diterbitkan administrator Google Workspace untuk mailbox tersebut. Jangan
menggunakan password pribadi yang disimpan di source control.

Untuk development, gunakan `EMAIL_ENABLED=false`. Untuk production, isi secret
password melalui secret manager atau environment deployment lalu restart backend.

Jika SMTP gagal, akun tetap tersimpan dan backend mencatat error tanpa
mengembalikan password atau credential ke response API.
