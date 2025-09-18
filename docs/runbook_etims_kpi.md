# Runbook: eTIMS Invoices & Vendor KPIs

Owner: Compliance/Operations

Timezone: Africa/Nairobi

## Feature Flags

- `ETIMS_ENABLED` (default: True in DEBUG, False otherwise)
- `KPIS_ENABLED`  (default: True in DEBUG, False otherwise)

Set via environment variables. Example:

```
ETIMS_ENABLED=true
KPIS_ENABLED=true
```

## eTIMS Invoice Submission

Pre-submit guards (hard block):
- Org must have a valid `kra_pin`.
- Org `tax_status` must be `VERIFIED`.

If the guard fails, the submission is rejected with error code `ORG_NOT_VERIFIED` and metric `invoices_rejected{reason="org_not_verified"}` is incremented.

### Replay Strategy (Sandbox)
1. Fix the org’s tax status (update KRA PIN and set `tax_status=VERIFIED`).
2. Re-run the management command for the org:
   `python manage.py submit_invoices --org <ORG_ID> --since 7`

### Metrics
- Counters:
  - `invoices_submitted{status=accepted|rejected}`
  - `invoices_rejected{reason=feature_disabled|org_not_verified|org_check_failed}`
- Histogram:
  - `etims_latency{status=...}` (seconds)

### Observability
- Structured logs on submission:
  - logger: `metrics` and `invoicing.services.etims`
  - includes status and timing

## Vendor KPIs

Scheduled job (Celery beat): `00:30` Africa/Nairobi.

- Task: `vendor_app.tasks.aggregate_kpis_daily_all`
- Metrics:
  - `kpi_jobs_success{org_id}`
  - `kpi_jobs_fail{org_id}`

### Backfill Script
To backfill historical KPIs, run the daily aggregator for a date range in a loop (example pseudocode):

```
from datetime import date, timedelta
from vendor_app.kpi import aggregate_kpis_daily

start = date(2025, 1, 1)
end = date(2025, 3, 31)
d = start
while d <= end:
    for org_id in VendorOrg.objects.values_list('id', flat=True):
        aggregate_kpis_daily(org_id, for_date=d)
    d += timedelta(days=1)
```

## Health/Readiness

- `/healthz` – basic liveness
- `/readyz` – pings Redis and reports Celery queue depth (`celery` list)

Expected JSON (healthy):

```
{
  "status": "ok",
  "redis": {"ok": true, "queue_depth": 0}
}
```

## Common Issues

- `ETIMS disabled` – enable flag and retry.
- `ORG_NOT_VERIFIED` – set valid KRA PIN and `tax_status=VERIFIED` on the org.
- KPI job skipped – enable `KPIS_ENABLED`.

