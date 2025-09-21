# DevOps Guide: eTIMS & KPIs

## Environment Variables
- `ETIMS_ENABLED` (default on in DEBUG): enable invoice submission.
- `KPIS_ENABLED` (default on in DEBUG): enable KPI endpoints and jobs.
- `ETIMS_CLIENT_CLASS` (optional): dotted path for client implementation.
  - Default: `invoicing.services.etims.SandboxEtimsClient`
  - Real:    `invoicing.services.etims.RealEtimsClient`
- `ETIMS_BASE_URL`, `ETIMS_API_KEY` (used by RealEtimsClient)
- `REDIS_URL` (required for `/readyz` and Celery broker)

## Celery
- Beat schedule: daily KPI aggregation at 00:30 Africa/Nairobi.
- Task: `vendor_app.tasks.aggregate_kpis_daily_all`

Run example:
```
celery -A Rahim_Online_ClothesStore beat -l info
celery -A Rahim_Online_ClothesStore worker -l info -Q default
```

## Redis
- Required for Channels and Celery in production.
- `/readyz` pings Redis and reports basic Celery queue depth.

## PDF Rendering
- For CSV/PDF downloads, reportlab is optional; a fallback PDF is generated when missing.

## OpenAPI Docs
- Served at `/apis/v1/docs/`.
- Schema at `/apis/v1/schema/`.
