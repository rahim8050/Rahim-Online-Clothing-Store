# Kenya Payments: M-PESA Daraja & Paystack

This app supports M-PESA STK callbacks and Paystack webhooks with idempotency and org-level settlement.

## Security
- Paystack: HMAC-SHA512 of raw request body using `PAYSTACK_SECRET_KEY`. Header: `X-Paystack-Signature`.
- M-PESA: Basic structural validation; recommend additional IP allowlisting or access token verification at the edge (proxy).
- All webhook payloads are persisted into `payments_paymentevent` with `body_sha256` for deduplication & audit.

## Org Settlement
- `VendorOrg` fields:
  - `org_commission_rate` (e.g. 0.02 for 2%)
  - `org_payout_channel` (`mpesa`|`bank`)
- On payment success:
  - `Transaction` updated with `gross_amount`, `fees_amount` (default 0), `commission_amount`, `net_to_vendor`, and bound to `vendor_org`.
  - `PaymentEvent` row created (raw payload + sha256).
  - `Payout` row created per Transaction (OneToOne) with `amount = net_to_vendor`.

## Webhook Endpoints
- `/webhook/paystack/` (payments.views.PaystackWebhookView)
- `/webhook/mpesa/` (payments.views.MPesaWebhookView)

Both are idempotent via raw-body SHA-256 (`accept_once`), safe to retry.

## Local Testing
```
export PAYSTACK_SECRET_KEY=sk_test_xxx
curl -X POST http://127.0.0.1:8000/webhook/paystack/ \
  -H 'Content-Type: application/json' \
  -H "X-Paystack-Signature: $(python - <<PY\nimport hmac,hashlib,sys;raw=b'{"event":"charge.success","data":{"reference":"ref-1","status":"success"}}';print(hmac.new(b"'+$env:PAYSTACK_SECRET_KEY+'",raw,hashlib.sha512).hexdigest())\nPY)" \
  --data-binary '{"event":"charge.success","data":{"reference":"ref-1","status":"success"}}'

curl -X POST http://127.0.0.1:8000/webhook/mpesa/ \
  -H 'Content-Type: application/json' \
  --data-binary '{"Body":{"stkCallback":{"MerchantRequestID":"ref-1","ResultCode":0,"CallbackMetadata":{"Item":[{"Name":"MpesaReceiptNumber","Value":"XYZ"}]}}}}'
```

## Operations
- Purge stale idempotency keys:
  `python manage.py purge_idempotency_keys --days 14`

## Notes
- Provider fees parsing is pluggable; by default fees=0. Set from gateway payloads if/when available.
