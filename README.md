# Order live tracking and DRF API v1

Run the ASGI server with Daphne or Django runserver:

```bash
python manage.py runserver 8000
# or
daphne -b 127.0.0.1 -p 8000 Rahim_Online_ClothesStore.asgi:application
```

Assign warehouses to pending items:

```bash
python manage.py assign_warehouses_to_items
```

Quick manual WS test from the browser console:

```javascript
const ws = new WebSocket('ws://127.0.0.1:8000/ws/delivery/track/DELIVERY_ID/');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

Replace `DELIVERY_ID` with a real identifier. Messages follow a unified schema:

```
{"type": "position_update", "lat": 1.23, "lng": 4.56}
{"type": "status", "status": "EN_ROUTE"}
```

Redis (set via `REDIS_URL`) powers the channel layer and cache; configure it in production with password/SSL as needed.

## DRF API v1

- OpenAPI schema: `GET /apis/v1/schema/`
- Swagger UI: `GET /apis/v1/docs/`
- JWT auth:
  - `POST /apis/v1/auth/jwt/create/` {"username","password"}
  - `POST /apis/v1/auth/jwt/refresh/` {"refresh"}

### Optional HMAC for catalog reads
You can protect `GET /apis/v1/catalog/*` with a signed request using custom headers:
- `X-Api-KeyId`: public key identifier
- `X-Api-Timestamp`: ISO8601 or unix seconds (UTC)
- `X-Api-Signature`: hex HMAC-SHA256 of canonical string

Canonical string to sign:
```
{timestamp}\n{METHOD}\n{PATH_WITH_QUERY}\n{sha256_hex(body)}
```

Keys live in `settings.API_KEYS`, e.g.:
```
API_KEYS = {
  "demo-key": {"secret": "<base64/hex/plain-secret>", "scopes": ["catalog:read"]}
}
```
Requests with a valid signature and `catalog:read` scope pass via `HasScope('catalog:read')` even without user auth. Otherwise, normal DRF permissions (JWT/Session) apply.

Mounted routers:
- Catalog: `/apis/v1/catalog/` (categories, products)
- Cart: `/apis/v1/cart/` (carts + actions)
- Orders: `/apis/v1/orders/` (orders + checkout)
- Payments: `/apis/v1/payments/` (checkout init)
- Users: `/apis/v1/users/` (me)

Example cURL:
```
curl -X POST http://127.0.0.1:8000/apis/v1/auth/jwt/create/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"pass"}'

curl http://127.0.0.1:8000/apis/v1/catalog/products/?search=shirt \
  -H "Authorization: Bearer $ACCESS"
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

## DRF API v2 (Cart)

- User carts (authenticated) live under `/apis/v2/cart/` and are strictly scoped to the current user. Exactly one ACTIVE cart per user is enforced by code and a DB constraint.
- Guest carts (anonymous) live under `/apis/v2/cart/guest/` and are addressed only via a signed cookie `guest_cart_id` (7 days, HttpOnly, SameSite=Lax).

Guest endpoints (AllowAny):
- `POST /apis/v2/cart/guest/carts/my_active/` → create or return the cookie-bound cart; sets `guest_cart_id` cookie when created.
- `POST /apis/v2/cart/guest/carts/{id}/add_item/` { product, quantity }
- `POST /apis/v2/cart/guest/carts/{id}/update_item/` { item_id, quantity }
- `POST /apis/v2/cart/guest/carts/{id}/remove_item/` { item_id }
- `POST /apis/v2/cart/guest/carts/{id}/clear/`

Login merge flow:
- On `user_logged_in`, the project merges the guest cart (if any) into the user's ACTIVE cart by summing quantities (no duplicates). The guest cart is deleted afterwards.
- The `guest_cart_id` cookie is cleared after authentication by `cart.middleware.ClearGuestCookieOnLoginMiddleware`.

Security notes:
- Guest endpoints never accept arbitrary cart IDs; they derive the cart solely from the signed cookie and then confirm the path `{id}` matches.
- User endpoints remain `IsAuthenticated` only and return 404 for other users' carts.

