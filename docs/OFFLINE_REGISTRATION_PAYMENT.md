# Offline Registration Payment and Ticket Issuance

## Purpose

An already registered participant may pay outside the platform by cash, bank
transfer, static QR, EDC, or another approved offline channel. Only an
admin/organizer records this payment. The payment is attached to the participant's
main registration order and a ticket is issued after full reconciliation.

## Participant search for Manual Payments

The `/admin/manual-payments` page searches by participant name, email, or
organization using an admin/organizer access token:

```http
GET /api/v1/admin/reports/participants?page=1&size=100&search=anwar&locale=en
Authorization: Bearer <admin-or-organizer-token>
```

Illustrative response excerpt; the email and IDs below are example values.
Other participant fields, purchase fields, and response metadata are omitted:

```json
{
  "success": true,
  "data": [
    {
      "participant_id": "11111111-1111-4111-8111-111111111111",
      "user_id": "22222222-2222-4222-8222-222222222222",
      "registration_id": "33333333-3333-4333-8333-333333333333",
      "full_name": "Anwar Sucipto",
      "email": "anwar@example.com",
      "packages": [
        { "registration_id": null },
        { "registration_id": "33333333-3333-4333-8333-333333333333" }
      ]
    }
  ],
  "meta": { "page": 1, "size": 100, "total": 1, "pages": 1 }
}
```

Each purchase exposes its order's `registration_id` as a UUID string or `null`.
The participant-level `registration_id` is the first non-null value among the
returned purchases after report filters. It does not identify the latest or
unpaid registration. When multiple registrations exist, select the registration
for the intended event and purchase instead of relying on this summary alone.

Use the selected registration UUID in the offline-payment endpoint below.
`participant_id`, `user_id`, and email cannot replace it. If `registration_id`
is `null`, disable payment submission and ask the organizer to select or complete
the relevant registration. A null value means no returned purchase links to a
registration; an existing registration without a linked order may still exist.
Never submit to `/registrations/null/offline-payments`.

A successful search only resolves participant data; the offline-payment endpoint
still validates registration and payment eligibility. End the search loading
state on errors, including `401` for missing/invalid/expired authentication and
`403` for insufficient permissions.

## Endpoint

```http
POST /api/v1/admin/registrations/{registration_id}/offline-payments
Authorization: Bearer <admin-or-organizer-token>
Content-Type: application/json
```

```json
{
  "payment_method": "cash",
  "amount": 7500000,
  "currency": "IDR",
  "receipt_number": "CASH-IWBIF-2026-00125",
  "paid_at": "2026-08-30T15:30:00+07:00",
  "notes": "Cash received at the event secretariat"
}
```

Supported methods are `cash`, `manual_transfer`, `manual_qr_code`, `edc`, and
`other_offline`. `amount` may be omitted; the backend then uses the exact
outstanding balance. If supplied, it must equal `remaining_amount`. This endpoint
is deliberately a full-settlement operation so that its successful response can
safely include a ticket.

## Reconciliation and coexistence with gateway payments

The backend locks the registration, resolves its main order, and creates that
order from the registered main-package snapshot only if a legacy registration
has no order. It then calculates:

```text
remaining_amount = main_order.total_amount - successful_payment_aggregate
```

Previously successful Midtrans/DOKU parts remain credited. The offline payment
covers only the remainder. Overpayment and underpayment are rejected. Additional
package orders are never selected as the main order and cannot make the core
registration eligible.

## Idempotency and audit

- `receipt_number` is globally unique and normalized to uppercase.
- Retrying the same receipt for the same registration returns the existing
  payment/ticket and does not create a second financial record.
- Reusing the receipt for another registration returns
  `OFFLINE_RECEIPT_ALREADY_USED`.
- The payment stores `confirmed_by`, `offline_receipt_number`, `paid_at`, method,
  amount, notes, and a `PaymentWebhookEvent` audit record.
- A successful payment is not hard-deleted; correction must use the established
  financial cancellation/refund process.

## Ticket behavior

After reconciliation confirms the main order is `paid`, the backend returns the
existing ticket or issues one. Ticket issuance is idempotent because a
registration can have only one active ticket record. A payment failure never
renders a ticket.

## Response

The response contains the canonical platform `order`, the offline `payment`, and
the `ticket`. Frontend/admin UI should render the ticket only from this successful
response or a subsequent ticket query.

## Legacy endpoint distinction

`POST /api/v1/admin/orders/{order_id}/confirm-manual-payment` remains available
for compatibility. The new registration endpoint is preferred for walk-in cash
and assisted payment because it resolves the main order, calculates gateway
credits, enforces a unique receipt, and returns the ticket.

## Production

Deploy the participant-report change in `app/modules/participants/reporting.py`
alongside the Manual Payments frontend that consumes `registration_id`. This
response-field addition uses existing order data and needs no new migration.
Smoke-test the authenticated search above and verify `registration_id` exists at
both participant and purchase levels; also verify the UI handles `null`.

Apply Alembic revision `202608300040`. Verify the receipt unique constraint and
`confirmed_by` foreign key, then smoke-test cash with no prior payment, cash after
a partial gateway payment, duplicate receipt retry, receipt reuse rejection, and
automatic ticket return.
