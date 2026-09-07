# DOKU Checkout: duplicate-payment protection

New hosted payments use `POST /api/v1/payments/doku/checkout` with `order_id`.
The backend sets `payment_type=doku_checkout`, creates an IDR bill of at most
Rp9,000,000, and leaves method selection to DOKU. Existing null-type hosted
payments and the former card-only checkout remain recognizable.

## Reservation and retry behavior

1. Lock the owned order before reading attempts. The legacy registration route
   also serializes requests before an order exists. Webhooks acquire order then
   payment locks, matching resume/cancel operations.
2. Inspect all non-deleted payment attempts, across providers and sequences.
   An unresolved VA, QRIS, manual, or other gateway attempt blocks a new bill.
   One unexpired hosted checkout can be reused with its stored amount/sequence.
3. Calculate the next amount from the verified remaining balance. The configured
   `QRIS_SEGMENT_LIMIT_IDR` may lower the cap but cannot raise it above Rp9,000,000.
   Exactly Rp9,000,000 is one payment; Rp20,000,000 is Rp9m + Rp9m + Rp2m.
4. Persist the payment ID, provider invoice, original request ID, expiry and
   `created` status, then commit before contacting DOKU. This releases the order
   lock while leaving a durable reservation for subsequent requests/webhooks.
5. After the provider responds, reload the payment under lock. Store the URL and
   only transition `created` to `pending`; a verified success is never undone by
   a slower checkout response or a later failure/expiry notification.

Timeouts, malformed responses, and uncertain provider errors retain the reservation.
Retry returns `PAYMENT_AWAITING_RECONCILIATION`, without another DOKU request.
Local clock expiry alone never clears an unresolved reservation. A verified final
expiry allows a new attempt with a new invoice for the same unpaid sequence.

## Webhooks and recovery

DOKU Checkout permits changing method after a failed channel attempt. Hosted
`FAILED`, `TIMEOUT`, `REDIRECT`, and `PENDING` notifications leave payment pending;
`SUCCESS` remains monotonic. Direct VA failure behavior remains separate.
Signatures, invoice lookup, notified amount, and event deduplication remain in use.

Reference: [DOKU notification best practices](https://developers.doku.com/get-started-with-doku-api/notification/best-practice).

For an unresolved reservation, inspect `provider_order_id` and `external_id`
(the original DOKU Request-Id) using the provider dashboard or
[Check Status API](https://developers.doku.com/get-started-with-doku-api/check-status-api/non-snap).
Reconcile verified provider evidence through the existing organizer process.
Do not delete the reservation or mark it failed merely because HTTP timed out.
Missing credentials fail before committing a reservation. An explicit HTTP error
is conservatively retained too, because this code does not classify provider error
bodies into safely retryable outcomes. Automated provider status polling is not
introduced by this change.

## Rollout and validation

No schema migration is required. Deploy the backend code together with the hosted
Checkout frontend. Reconcile unresolved old attempts before issuing replacement
invoices, including legacy hosted attempts previously marked failed by a channel
failure. This change does not rewrite historical payment rows or deploy itself.

`tests/test_doku_checkout.py` covers persistence before I/O, interleaved requests,
timeout/retry, missing URL, legacy/provider collisions, local versus verified
expiry, exact cap boundaries, remaining balances, and webhook/response ordering.
Concurrency tests model the database lock with an asyncio lock; the existing
repository test verifies generated PostgreSQL `FOR UPDATE OF orders` SQL.
Live PostgreSQL contention and a full DOKU sandbox payment must still be checked
in the deployment environment.
