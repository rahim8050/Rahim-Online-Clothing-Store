# Admin Guide: Kenya Compliance Features

## Verifying KRA PIN
- Navigate to Admin → Vendor Orgs → select org
- Set a valid `kra_pin` (format `A123456789B`) and change `tax_status` to `VERIFIED`.
- Save; audit log entries are written for sensitive changes.

## Enabling Features
- `ETIMS_ENABLED`: gates invoice submission endpoints and jobs.
- `KPIS_ENABLED`: gates KPI endpoints and disables scheduled KPI jobs when off.

Set via environment variables:
```
ETIMS_ENABLED=true
KPIS_ENABLED=true
```

## Roles & Access
- Only MANAGER or OWNER may submit or download invoices for an org.
- Only MANAGER or OWNER may view KPIs.

