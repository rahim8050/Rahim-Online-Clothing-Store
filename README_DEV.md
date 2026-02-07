# Login Flow & Sites Quickstart

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py migrate sites  # ensure django_site exists
python manage.py set_site_domain  # sync SITE_DOMAIN/SITE_NAME into DB
python manage.py createsuperuser  # optional admin access
python manage.py runserver
```

For tests and linting, install `requirements-dev.txt`.

If the Sites table is empty or uses the wrong domain, override via env vars:

```bash
export SITE_DOMAIN=127.0.0.1:8000
export SITE_SCHEME=http
python manage.py set_site_domain
```

When the MySQL user cannot create the automatic `test_<dbname>` schema,
update grants for your account or create a dedicated test user with the
`CREATE` privilege before running `manage.py test`.

To run the pytest suite using the sqlite test settings:

```bash
DJANGO_SETTINGS_MODULE=tests.django_test_settings pytest -q
```

## Session to JWT (UI helper)

Server-rendered pages can exchange their authenticated session for a short-lived
JWT access token:

```
POST /apis/auth/session-jwt/
```

Response:

```
{"access": "<jwt>", "expires_in": 900, "token_type": "Bearer"}
```

Example (browser):

```js
const r = await fetch("/apis/auth/session-jwt/", {
  method: "POST",
  headers: { "X-CSRFToken": getCookie("csrftoken") },
  credentials: "same-origin",
});
const { access } = await r.json();
// Use access token on /apis/v1/* calls:
// Authorization: Bearer <access>
```
