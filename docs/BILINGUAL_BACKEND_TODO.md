# Backend Bilingual `en` / `zh-CN` — TODO dan Acceptance Checklist

Dokumen ini adalah sumber checklist pekerjaan bilingual backend. Locale canonical:

- `en` — English sekaligus fallback utama.
- `zh-CN` — Simplified Chinese.

Nilai mesin seperti status, provider, trigger, `error.code`, identifier, dan
`allowed_actions` tidak boleh diterjemahkan.

## 1. Fondasi locale

- [x] Menambahkan `users.preferred_locale` dengan default `en`.
- [x] Menerima `preferred_locale` pada registrasi akun.
- [x] Mengizinkan perubahan `preferred_locale` melalui update profil.
- [x] Mendukung query `?locale=en|zh-CN`.
- [x] Mendukung header `Accept-Language`.
- [x] Menetapkan prioritas query locale, header, lalu fallback `en`.
- [x] Menormalisasi alias `zh`, `zh_CN`, dan `zh-Hans` menjadi `zh-CN`.
- [x] Mempertahankan nilai mesin tetap canonical.
- [x] Menambahkan `Content-Language` pada response HTTP.
- [x] Menentukan perilaku final untuk locale tidak valid: fallback atau error
  `422`; saat ini backend menggunakan fallback `en`.

## 2. Pesan response dan error

- [x] Menyediakan mekanisme lokalisasi pesan success/error tanpa mengubah envelope.
- [x] Mempertahankan `error.code` agar frontend tidak bergantung pada teks.
- [x] Menyediakan terjemahan Mandarin untuk pesan autentikasi utama.
- [x] Menambahkan katalog Mandarin berbasis `error.code` untuk domain utama.
- [x] Menginventarisasi pesan hard-coded dengan audit AST yang dapat dijalankan ulang.
- [ ] Mengganti pesan hard-coded dengan message key atau katalog terpusat.
- [ ] Melengkapi terjemahan `zh-CN` untuk semua message key.
- [x] Melokalisasi error validasi Pydantic umum dan menyediakan fallback Mandarin aman.
- [x] Menyeragamkan error `HTTPException` dengan error contract aplikasi.
- [x] Menambahkan pengujian bahwa status HTTP dan error code sama pada kedua locale.

## 3. Konten dinamis

Gunakan tabel translation terpisah atau desain ekuivalen; hindari penambahan
kolom seperti `name_en`, `name_zh` pada setiap tabel tanpa keputusan arsitektur.

- [x] Menetapkan schema translation, fallback, constraint locale, dan audit fields.
- [x] Event: `name`, `description`, `venue_name`, dan `venue_address`.
- [x] Product/store item: `name` dan `description`.
- [x] Delegate/exhibitor package: `name` dan `description`.
- [x] Package rate: `name`.
- [x] Package facility: `name`, `description`, dan `unit` bila perlu.
- [x] Event activity dan business-matching slot label.
- [x] Session/agenda: title, description, room/track label bila merupakan konten.
- [x] Speaker: display name tidak diterjemahkan; bio, title, dan organization dapat
  diberi terjemahan sesuai kebutuhan konten.
- [x] Announcement: title dan body.
- [x] Certificate title jika sertifikat harus mengikuti locale penerima.
- [x] Menyediakan endpoint admin untuk create/update/delete translation.
- [x] Menambahkan locale dan informasi fallback pada response konten.
- [x] Memastikan snapshot order mempertahankan nama pada saat checkout dan tidak
  berubah karena translation diedit kemudian.

## 4. Email dan notifikasi

- [x] Menyimpan template email terpisah untuk `en` dan `zh-CN`.
- [x] Menyediakan default template pada kedua locale untuk seluruh trigger.
- [x] Menggunakan `user.preferred_locale` untuk email otomatis.
- [x] Menyimpan locale yang digunakan pada log email.
- [x] Mendukung query locale pada admin list/update/preview/test-send dan log.
- [x] Memastikan fallback eksplisit `preferred locale -> en` jika template tidak
  tersedia; template yang dimatikan tetap tidak dikirim.
- [x] Melokalisasi `event_name`, `package_name`, package rate, dan venue dari sumber
  konten dinamis sebelum render email.
- [x] Menambahkan preview yang memperlihatkan locale dan fallback yang digunakan.
- [x] Menetapkan locale email mengikuti locale akun; preferensi terpisah belum diperlukan.

## 5. Endpoint dan kontrak frontend

- [x] Mendokumentasikan `preferred_locale`, query locale, dan `Accept-Language`.
- [x] Mendokumentasikan locale template email.
- [x] Menambahkan contoh response lengkap `en` dan `zh-CN` untuk editor speaker.
- [x] Menambahkan parameter locale global ke OpenAPI description.
- [x] Mendokumentasikan field yang diterjemahkan dan field yang tetap canonical.
- [x] Mendokumentasikan fallback konten dinamis untuk frontend.
- [x] Menetapkan query locale untuk language switch frontend; `Accept-Language`
  tetap didukung sebagai fallback request.

## 6. Database dan migrasi

- [x] Menambahkan migrasi `202608290035` untuk user locale dan email locale.
- [x] Menambahkan migrasi `202608290036` untuk content translation.
- [x] Menambahkan migrasi `202608290037` untuk database locale constraints.
- [x] Menjaga satu Alembic head.
- [x] Membuat migrasi translation untuk konten dinamis.
- [x] Mempertahankan konten lama sebagai field sumber fallback tanpa duplikasi backfill.
- [x] Memastikan downgrade mempertahankan source canonical dan mendokumentasikan
  bahwa translation locale akan dihapus.
- [ ] Menguji migrasi pada salinan database PostgreSQL production.
- [x] Memvalidasi SQL offline migrasi bilingual `202608280034 -> 202608290037`.
- [ ] Memeriksa index dan query plan untuk lookup translation.

## 7. Pengujian

- [x] Unit test normalisasi locale.
- [x] Unit test prioritas query terhadap header.
- [x] Unit test response Mandarin tanpa mengubah error code.
- [x] Unit test kontrak `preferred_locale`.
- [x] Memastikan semua trigger memiliki template `en` dan `zh-CN`.
- [x] Regression suite terakhir: 98 test lulus.
- [x] Test integrasi ASGI endpoint menggunakan `Accept-Language: zh-CN`.
- [x] Test integrasi ASGI endpoint menggunakan `?locale=zh-CN`.
- [x] Test fallback translation konten dinamis.
- [x] Test service CRUD translation, audit actor, dan permission organizer/participant.
- [x] Test email English, Simplified Chinese, dan fallback template.
- [x] Test checkout/order snapshot pada locale berbeda.
- [x] Test bahwa hasil mesin webhook payment tidak bergantung pada locale.
- [x] Test OpenAPI locale parameter dan response envelope bilingual utama.

## 8. Deployment dan observability

- [ ] Backup database sebelum migration production.
- [ ] Jalankan `alembic upgrade head` pada staging.
- [ ] Smoke test akun `en` dan `zh-CN` di staging.
- [ ] Smoke test email kedua locale melalui SMTP production-equivalent.
- [x] Tambahkan locale ke structured request log tanpa header/body/data sensitif.
- [ ] Monitor error rate, missing translation, dan email failure setelah deploy.
- [ ] Jalankan migration production dan restart application service.
- [ ] Verifikasi frontend Simplified Chinese terhadap API production.

## Definition of Done

Pekerjaan backend bilingual baru dapat dinyatakan selesai seluruhnya jika:

- [ ] Semua konten publik yang disepakati memiliki translation `en` dan `zh-CN`.
- [ ] Semua endpoint terkait mengembalikan locale yang benar dengan fallback konsisten.
- [ ] Semua pesan pengguna dan email utama tersedia pada kedua bahasa.
- [ ] Nilai mesin tidak berubah antar-locale.
- [ ] Migration staging dan production tervalidasi.
- [ ] Seluruh test unit, integrasi, migration, dan smoke test lulus.
- [ ] Dokumentasi frontend dan backend sesuai implementasi aktual.
