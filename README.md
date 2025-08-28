# Order live tracking

Run the ASGI server with Daphne:

```bash
daphne -b 127.0.0.1 -p 8000 Rahim_Online_ClothesStore.asgi:application
```

Assign warehouses to pending items:

```bash
python manage.py assign_warehouses_to_items
```

Quick manual test from the browser console:

```javascript
const ws = new WebSocket('ws://127.0.0.1:8000/ws/delivery/track/DELIVERY_ID/');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

Replace `DELIVERY_ID` with a real identifier.

Messages follow a unified schema:

```
{"type": "position_update", "lat": 1.23, "lng": 4.56}
{"type": "status", "status": "EN_ROUTE"}
```

Redis (set via `REDIS_URL`) powers the channel layer and cache; configure it in production with password/SSL as needed.

## Geoapify setup

The checkout address autocomplete relies on Geoapify through a server-side proxy.
Set the `GEOAPIFY_API_KEY` environment variable in production and restrict the
key in the Geoapify dashboard to your backend domain. Only the backend calls
Geoapify; the key is never exposed to the browser.

## Roles & permissions

The project provisions Django groups for five roles: **Admin**, **Customer**,
**Vendor**, **Vendor Staff**, and **Driver**.

Apply migrations and sync the role groups:

```bash
python manage.py migrate
python manage.py sync_roles
```

Running `sync_roles` multiple times is safe and updates any missing groups or
permissions.

### Smoke test

```bash
python manage.py migrate
python manage.py sync_roles
python manage.py test users
```

## Auth tokens

Obtain JWTs for API access:

```
POST /api/auth/token/ {"username": "<user>", "password": "<pass>"}
POST /api/auth/token/refresh/ {"refresh": "<token>"}
```

Dashboards are available for vendors and drivers at `/users/vendor-dashboard/`
and `/users/driver-dashboard/` respectively. Matching read-only APIs live under
`/api/vendor/products/` and `/api/driver/deliveries/`.

