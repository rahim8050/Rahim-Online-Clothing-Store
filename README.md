# Order Live Tracking & DRF API (v1/v2)

This document consolidates the live‑tracking (WebSocket) and REST API runbook for the project. All merge markers have been resolved and duplicated blocks removed.

---

## Quick Start (Dev)

```bash
pip install -r requirements.txt
python manage.py makemigrations   # should result in no model changes
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 8000    # http://127.0.0.1:8000/
# OR ASGI via Daphne
# daphne -b 127.0.0.1 -p 8000 Rahim_Online_ClothesStore.asgi:application
```

### Redis / Channel Layer

* In development you may use the in‑memory channel layer.
* In production, set `REDIS_URL` to enable Redis for Channels and cache.

  * Configure password/SSL as required by your host (e.g., `rediss://:password@host:port/0`).

### Warehouse Assignment (utility)

Assign warehouses to pending items:

```bash
python manage.py assign_warehouses_to_items
```

---

## Live Tracking (WebSocket)

**Endpoint**: `/ws/delivery/track/<DELIVERY_ID>/`

**Manual browser test** (replace `DELIVERY_ID`):

```javascript
const wsScheme = location.protocol === "https:" ? "wss" : "ws";
const ws = new WebSocket(`${wsScheme}://${location.host}/ws/delivery/track/DELIVERY_ID/`);
ws.onopen = () => console.log("WS connected");
ws.onmessage = (e) => console.log("WS msg:", JSON.parse(e.data));
ws.onclose = () => console.log("WS closed");
```

**Message schema** (examples):

```json
{"type": "position_update", "lat": 1.23, "lng": 4.56}
{"type": "status", "status": "EN_ROUTE"}
```

> **Notes**
>
> * Ensure ASGI is active (Daphne/Uvicorn) in production. Django’s dev server is fine for local.
> * Verify your Channels routing and auth middleware if you gate driver/customer access.
> * Throttling, lat/lng quantization, and validation should be enforced server‑side (already implemented in consumers).

---

## DRF API v1

* **OpenAPI schema**: `GET /apis/v1/schema/`
* **Swagger UI**: `GET /apis/v1/docs/`

### Authentication (JWT)

* **Create**: `POST /apis/v1/auth/jwt/create/` with body `{ "username": "<user>", "password": "<pass>" }`
* **Refresh**: `POST /apis/v1/auth/jwt/refresh/` with body `{ "refresh": "<token>" }`

**Example**

```bash
# Get tokens
curl -sS -X POST http://127.0.0.1:8000/apis/v1/auth/jwt/create/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"pass"}'

# Use access token
curl -sS 'http://127.0.0.1:8000/apis/v1/catalog/products/?search=shirt' \
  -H "Authorization: Bearer $ACCESS"
```

### Routers Mounted

* **Catalog**: `/apis/v1/catalog/` (categories, products)
* **Cart**: `/apis/v1/cart/` (carts + actions)
* **Orders**: `/apis/v1/orders/` (orders + checkout)
* **Payments**: `/apis/v1/payments/` (checkout init)
* **Users**: `/apis/v1/users/` (profile/me)

### Optional HMAC for Catalog Reads

To allow signed, key‑based *read‑only* access (without user auth), enable HMAC:

**Headers**

* `X-Api-KeyId`: public key identifier
* `X-Api-Timestamp`: ISO‑8601 or unix seconds (UTC)
* `X-Api-Signature`: hex HMAC‑SHA256 over canonical string

**Canonical string**

```
{timestamp}\n{METHOD}\n{PATH_WITH_QUERY}\n{sha256_hex(body)}
```

**Settings**

```python
API_KEYS = {
  "demo-key": {"secret": "<base64/hex/plain-secret>", "scopes": ["catalog:read"]}
}
```

Requests with a valid signature and `catalog:read` scope pass via `HasScope('catalog:read')`. Otherwise normal DRF permissions (JWT/Session) apply.

**Example (Python sign)**

```python
import hmac, hashlib

def sign_request(secret: bytes, timestamp: str, method: str, path_with_query: str, body: bytes) -> str:
    c = f"{timestamp}\n{method.upper()}\n{path_with_query}\n{hashlib.sha256(body or b'').hexdigest()}".encode()
    return hmac.new(secret, c, hashlib.sha256).hexdigest()
```


---
======
### Enterprise Vendor v1

Enterprise multi-tenant vendor capabilities are available in parallel under `/apis/v1/vendor/*` without breaking legacy routes.

- Tenancy: `VendorOrg` (organization) and `VendorMember` with org-scoped RBAC (OWNER, MANAGER, STAFF)
- Permissions: reusable DRF permission classes in `vendor_app/permissions.py`
- Throttling: org-scoped throttle key via `VendorOrgScopedRateThrottle` (configurable rates)
- Payments: org-aware commission, PaymentEvent raw payloads with body sha256, and Payout records

Docs:
- OpenAPI JSON: `/apis/v1/schema/?format=json`
- Swagger UI: `/apis/v1/docs/`
- Detailed guide: `docs/ENTERPRISE_VENDOR.md`
- Kenya payments notes: `docs/PAYMENTS_KE.md`

Quick cURL examples (JWT omitted for brevity):

1) Create an org (as authenticated user)

```
curl -X POST http://localhost:8000/apis/v1/vendor/orgs/ \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"name": "Rahim Traders"}'
```

2) Invite a member (MANAGER+)

```
curl -X POST http://localhost:8000/apis/v1/vendor/orgs/<org_id>/invite/ \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"user_id": 123, "role": "STAFF"}'
```

3) List members (STAFF+)

```
curl -H 'Authorization: Bearer <token>' \
  http://localhost:8000/apis/v1/vendor/orgs/<org_id>/members/
```

4) List org products and orders (STAFF+)

```
curl -H 'Authorization: Bearer <token>' http://localhost:8000/apis/v1/vendor/orgs/<org_id>/products/
curl -H 'Authorization: Bearer <token>' http://localhost:8000/apis/v1/vendor/orgs/<org_id>/orders/
```

5) Create products (legacy non-versioned route kept; provide owner_id and stock)

```
curl -X POST http://localhost:8000/apis/vendor/products/create/ \
  -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' \
  -d '{"name":"Tee","slug":"tee","price":"100.00","category":1,
        "owner_id": <owner_user_id>,
        "stock_allocations": [{"warehouse": 1, "quantity": 10}] }'
```

6) Kenya Webhooks (idempotent):

```
# Paystack
curl -X POST http://localhost:8000/webhook/paystack/ \
  -H 'Content-Type: application/json' \
  -H 'X-Paystack-Signature: <hmac-sha512>' \
  --data-binary @sample_paystack_success.json

# M-PESA STK Callback
curl -X POST http://localhost:8000/webhook/mpesa/ \
  -H 'Content-Type: application/json' \
  --data-binary @sample_mpesa_stk_callback.json
```

Runbook:
```
pip install -r requirements.txt
python manage.py makemigrations  # should be no model changes
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 8000
# Open http://127.0.0.1:8000/apis/v1/docs/
```


## DRF API v2 — Cart

* **User carts (authenticated)**: `/apis/v2/cart/` — strictly scoped to the current user. Enforced: exactly one **ACTIVE** cart per user (code + DB constraint).
* **Guest carts (anonymous)**: `/apis/v2/cart/guest/` — identified solely by a **signed** cookie `guest_cart_id` (7 days, HttpOnly, SameSite=Lax).

**Guest endpoints (AllowAny)**

* `POST /apis/v2/cart/guest/carts/my_active/` → create/return cookie‑bound cart; sets `guest_cart_id` when created.
* `POST /apis/v2/cart/guest/carts/{id}/add_item/` `{ product, quantity }`
* `POST /apis/v2/cart/guest/carts/{id}/update_item/` `{ item_id, quantity }`
* `POST /apis/v2/cart/guest/carts/{id}/remove_item/` `{ item_id }`
* `POST /apis/v2/cart/guest/carts/{id}/clear/`

**Login merge flow**

* On `user_logged_in`, merge guest → user ACTIVE cart by summing quantities (no duplicates). Delete guest cart afterward.
* `cart.middleware.ClearGuestCookieOnLoginMiddleware` clears `guest_cart_id` post‑auth.

**Security notes**

* Guest endpoints never accept arbitrary cart IDs; they derive the cart from the signed cookie, then assert path `{id}` matches.
* User endpoints require `IsAuthenticated`; other users’ carts return 404.

---

## Paystack Webhook Hardening

* Verify `x-paystack-signature` (lowercased/stripped) using **HMAC‑SHA512** over the **raw request body** with `PAYSTACK_SECRET_KEY`.
* Idempotency: compute SHA‑256 of the raw body and store on `orders.PaymentEvent`. Duplicate bodies ACK with 200 and cause no side‑effects.

**Endpoints**

* Project: `/webhook/paystack/` → `payments.views.PaystackWebhookView`
* Orders app: `orders:paystack_webhook` → `orders.views.paystack_webhook`

**Environment**

* `PAYSTACK_SECRET_KEY` = `sk_test_xxx` or `sk_live_xxx`
* `DJANGO_SETTINGS_MODULE` = `Rahim_Online_ClothesStore.settings`

**Local check**

```bash
python - <<'PY'
import hmac, hashlib
raw=b'{"event":"charge.success","data":{"reference":"ref_123","amount":30000,"currency":"KES"}}'
secret=b'sk_test_example'
print(hmac.new(secret, raw, hashlib.sha512).hexdigest())
PY
```

**Tests / Replay**

```bash
pytest -q
python manage.py test orders.tests.test_webhook_paystack -v
python manage.py replay_paystack --order 123 --status success --verbose-json
```

---

## Roles & Permissions

The project provisions Groups for five roles: **Admin**, **Customer**, **Vendor**, **Vendor Staff**, **Driver**.

**Sync roles**

```bash
python manage.py migrate
python manage.py sync_roles
```

* Safe to run repeatedly; missing groups/permissions are added idempotently.

**Smoke test**

```bash
python manage.py migrate
python manage.py sync_roles
python manage.py test users
```

> If vendor/driver dashboards are enabled in your build, they’re typically available at:
>
> * `/users/vendor-dashboard/`
> * `/users/driver-dashboard/`

---

## Troubleshooting

* **WS 403/CSRF**: Ensure correct auth middleware for Channels and that your origin/hosts are allowed.
* **Redis SSL**: Use `rediss://` for SSL endpoints and set CA certs if your host requires verification.
* **Docs 404**: Confirm DRF schema/Swagger URLs are included in `urls.py` under the `/apis/v1/` prefix.
* **JWT 401**: Check clock skew; refresh tokens if expired. Verify `AUTHENTICATION_BACKENDS` and SimpleJWT settings.

---

## Useful URLs (Dev)

* Swagger: `http://127.0.0.1:8000/apis/v1/docs/`
* OpenAPI JSON: `http://127.0.0.1:8000/apis/v1/schema/`
* Example search: `http://127.0.0.1:8000/apis/v1/catalog/products/?search=shirt`
* Live tracking (replace ID): `ws://127.0.0.1:8000/ws/delivery/track/<DELIVERY_ID>/`

---

**End of document.**
