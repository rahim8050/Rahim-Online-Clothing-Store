# Login Flow & Sites Quickstart

```bash
python manage.py migrate
python manage.py migrate sites  # ensure django_site exists
python manage.py set_site_domain  # sync SITE_DOMAIN/SITE_NAME into DB
python manage.py createsuperuser  # optional admin access
python manage.py runserver
python manage.py test -v 2
```

If the Sites table is empty or uses the wrong domain, override via env vars:

```bash
export SITE_DOMAIN=127.0.0.1:8000
export SITE_SCHEME=http
python manage.py set_site_domain
```

When the MySQL user cannot create the automatic `test_<dbname>` schema,
update grants for your account or create a dedicated test user with the
`CREATE` privilege before running `manage.py test`.
