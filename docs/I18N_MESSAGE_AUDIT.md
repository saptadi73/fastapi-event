# I18N Message Audit

Backend menyediakan audit AST untuk menginventarisasi literal pesan dan stable
error code tanpa menjalankan aplikasi:

```bash
python scripts/audit_i18n_messages.py
python scripts/audit_i18n_messages.py --details
```

Hasil audit terakhir:

- 194 literal pesan sukses unik.
- 169 stable error code unik.
- 209 literal pesan error unik.

Semua response `zh-CN` aman karena:

- Error menggunakan terjemahan khusus berdasarkan `error.code`, atau fallback
  Mandarin generik `请求无法处理（ERROR_CODE）`.
- Validasi field menggunakan terjemahan pola umum atau fallback
  `输入内容无效`.
- Pesan sukses yang belum memiliki copy khusus menggunakan `操作成功`.

Audit tetap dipertahankan untuk meningkatkan kualitas copy. Literal source boleh
tetap deskriptif untuk logika internal, tetapi frontend tidak boleh bergantung
pada teks tersebut. Prioritaskan penambahan copy khusus untuk auth, checkout,
payment, registration, speaker, session, dan business matching.

Script mengembalikan daftar deterministic sehingga hasil dapat dibandingkan pada
code review atau CI saat message baru ditambahkan.
