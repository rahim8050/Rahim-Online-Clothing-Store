# VendorStaff one-time maintenance

```bash
git switch -c fix/vendorstaff-0822
python manage.py makemigrations && python manage.py migrate
python manage.py audit_vendorstaff
python manage.py fix_vendorstaff
pytest -q -k vendorstaff
```

## Rollback

```bash
git restore .
python manage.py migrate users 0003
```
