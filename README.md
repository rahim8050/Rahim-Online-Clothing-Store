# Rahim Online Clothing Store — APIs & WebSockets

This document summarizes the API and WebSocket surfaces that exist in the repo right now, plus the minimum dev/runtime setup to exercise them.

---

## Quick Start (Dev)

```bash
python -m pip install -r requirements.txt
python manage.py makemigrations   # should result in no model changes
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 8000    # http://127.0.0.1:8000/
# OR ASGI via Daphne
# daphne -b 127.0.0.1 -p 8000 Rahim_Online_ClothesStore.asgi:application
```

For tests and linting, install `requirements-dev.txt`.

## Render Build + Static

Render build command:

```bash
bash scripts/render-build.sh
```

This runs `npm run build` for Vite output (`static/dist/assets/main.js`), compiles Tailwind to
`static/dist/styles.css`, verifies the JS exists, then runs `collectstatic --clear` and
`migrate --noinput`. The `static/dist/` directory is gitignored and must be built on Render.

### Redis / Channel Layer

* In development you may use the in-memory channel layer.
* In production, set `REDIS_URL` to enable Redis for Channels and cache.
  Runtime processes (web/worker) require it; management commands like
  `collectstatic`/`migrate` can run without it.
* On Render, set `REDIS_URL` on both the web service and any worker service.

  * Configure password/SSL as required by your host (e.g., `rediss://:password@host:port/0`).

### Warehouse Assignment (utility)

Assign warehouses to pending items:

```bash
python manage.py assign_warehouses_to_items
```

---

## WebSockets

### Delivery Tracking

**Endpoint**: `/ws/delivery/track/<DELIVERY_ID>/`

**Auth**: required. The consumer allows the assigned driver or the order owner.

**Manual browser test** (replace `DELIVERY_ID`):

```javascript
const wsScheme = location.protocol === "https:" ? "wss" : "ws";
const ws = new WebSocket(`${wsScheme}://${location.host}/ws/delivery/track/DELIVERY_ID/`);
ws.onopen = () => console.log("WS connected");
ws.onmessage = (e) => console.log("WS msg:", JSON.parse(e.data));
ws.onclose = () => console.log("WS closed");
```

**Incoming examples**

```json
{"type": "position_update", "lat": 1.23, "lng": 4.56}
{"type": "status", "status": "en_route"}
{"op": "ping"}
```

**Outgoing examples**

```json
{"type": "position_update", "lat": 1.23, "lng": 4.56, "status": "en_route"}
{"type": "status", "status": "picked_up"}
{"type": "pong"}
```

> **Notes**
>
> * Ensure ASGI is active (Daphne/Uvicorn) in production. Django’s dev server is fine for local.
> * Verify your Channels routing and auth middleware if you gate driver/customer access.
> * Throttling, lat/lng quantization, and validation should be enforced server‑side (already implemented in consumers).

### Notifications

**Endpoint**: `/ws/notifications/`

Anonymous clients join the `anon` group by default; authenticated users join `user_<id>`. The consumer emits a small `ws.hello` payload on connect and broadcasts messages from group sends with `type=notify`.

---

## DRF API v1

* **OpenAPI schema**: `GET /apis/v1/schema/`
* **Swagger UI**: `GET /apis/v1/docs/`

### Authentication (JWT)

* **Create**: `POST /apis/v1/auth/jwt/create/` with body `{ "username": "<user>", "password": "<pass>" }`
* **Refresh**: `POST /apis/v1/auth/jwt/refresh/` with body `{ "refresh": "<token>" }`

**Session → JWT helper (legacy UI bridge)**

* `POST /apis/auth/session-jwt/` (CSRF required; returns a short‑lived access token)

**Legacy auth endpoints**

* `POST /apis/auth/token/`
* `POST /apis/auth/token/refresh/`

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
* **Invoicing**: `/apis/v1/invoicing/`
* **Vendor (enterprise)**: `/apis/v1/vendor/`

### Auth Notes

* API authentication is JWT-based. Session auth is reserved for server-rendered UI flows.
* Some legacy `/apis/*` endpoints explicitly accept both Session + JWT auth.
* JWT obtain/refresh endpoints are rate-limited; prefer reusing access tokens until expiry.


---

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

* Verify `X-Paystack-Signature` using **HMAC‑SHA512** over the **raw request body** with `PAYSTACK_SECRET_KEY`.
* Idempotency for `/webhook/paystack/` uses `payments.IdempotencyKey` keyed by SHA‑256 of the raw body.
* Idempotency for `/orders/webhook/paystack/` uses `orders.PaymentEvent.body_sha256` and stores `Transaction.body_sha256`.

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
