# Production database migration

> Untuk rilis segmented QRIS/payment, ikuti urutan produksi lengkap pada
> `docs/SEGMENTED_QRIS_PAYMENT_IMPLEMENTATION.md`. Checkout harus dibekukan selama
> pergantian karena backend lama menganggap satu payment sukses sebagai pelunasan
> penuh. Revision target setelah segmented payment dan additional package order
> adalah `202608300039`.

## Bilingual revisions

Rangkaian bilingual saat ini berakhir di revision `202608290037`:

- `202608290035`: locale user serta template/log email.
- `202608290036`: content translation dinamis.
- `202608290037`: check constraint `en` dan `zh-CN`.

SQL PostgreSQL untuk rentang `202608280034:202608290037` telah lolos validasi
offline. Tetap lakukan backup dan uji pada salinan database staging sebelum
menjalankan `alembic upgrade head` di production.

Structured request log mencatat `request_id`, `locale`, method, path tanpa query,
status code, dan durasi. Header, request body, token, serta data pribadi tidak
dicatat oleh locale middleware.

Downgrade bilingual mempertahankan field source canonical pada event, speaker,
session, product, dan resource lain. Menurunkan melewati revision `202608290036`
akan menghapus tabel content translation; menurunkan melewati `202608290035`
akan menghapus template email non-English. Backup wajib dilakukan sebelum downgrade.

Run this procedure from the deployed backend repository. It applies every
committed Alembic revision, seeds the DOKU payment-channel catalog
idempotently, and verifies the final revision and core IWBIF tables.

## Before running

1. Back up the production PostgreSQL database and verify that it can be
   restored.
2. Deploy the intended backend commit and install `requirements.txt`.
3. Configure `APP_ENV=production` and the production `DATABASE_URL` in the
   server environment. Do not place credentials in this command or commit
   them to Git.
4. Stop concurrent deployment jobs. The application may remain online when
   migrations are backward compatible; otherwise use a maintenance window.

## Execute

From the repository root with its virtual environment activated:

```bash
python scripts/migrate_production.py --confirm-production
```

The script refuses to run unless `APP_ENV=production`, refuses a migration
tree with multiple heads, tests the database connection, executes
`alembic upgrade head`, runs `seed_payment_channels.py`, then checks
`alembic_version` and required tables.

To migrate schema without changing the payment-channel catalog:

```bash
python scripts/migrate_production.py --confirm-production --skip-payment-channel-seed
```

## Complete production seed

The complete IWBIF seed includes reference data plus example users,
registrations, successful payments, tickets, conversations, and business
matching records. Run it only when those records are intentionally required.
It is idempotent and does not reset passwords of accounts that already exist.

Set a strong, temporary password through the server secret environment (never
put it in Git or shell history), then run:

```bash
python scripts/migrate_production.py \
  --confirm-production \
  --seed-all \
  --confirm-demo-data
```

`IWBIF_SEED_PASSWORD` must contain at least 16 characters. The known local
demo password is rejected in production. Rotate or disable the seeded accounts
after verification. Running the command again updates reference/demo content
without duplicating its natural keys.
