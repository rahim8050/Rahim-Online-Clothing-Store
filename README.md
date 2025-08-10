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
const ws = new WebSocket('ws://127.0.0.1:8000/ws/track/ORDER_ID/ITEM_ID/');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

Replace `ORDER_ID` and `ITEM_ID` with real identifiers.

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

