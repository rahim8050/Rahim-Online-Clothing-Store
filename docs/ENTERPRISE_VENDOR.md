# Enterprise Vendor v1

Multi-tenant vendor foundations with org-scoped RBAC and parallel APIs.

## Concepts
- VendorOrg: organization (tenant) owned by a User
- VendorMember: membership with role OWNER|MANAGER|STAFF and `is_active`
- VendorProfile: legacy bridge mapping a vendor user -> primary org

## RBAC
- Permissions (`vendor_app/permissions.py`):
  - IsInOrg, IsOrgStaff, IsOrgManager, IsOrgOwner
- Role hierarchy: OWNER ≥ MANAGER ≥ STAFF

## API Surface
- `GET/POST /apis/v1/vendor/orgs/`
- `GET/PATCH /apis/v1/vendor/orgs/{id}/`
- `POST /apis/v1/vendor/orgs/{id}/invite/`
- `GET /apis/v1/vendor/orgs/{id}/members/`
- `DELETE /apis/v1/vendor/members/{id}/`
- `GET /apis/v1/vendor/orgs/{id}/orders/`
- `GET /apis/v1/vendor/orgs/{id}/products/`

Pagination: PageNumber (default page_size=20)
Throttle: `VendorOrgScopedRateThrottle` (scope `vendor.org`, configure rates in REST_FRAMEWORK)

## End-to-end Flow
1) Owner creates org (auto OWNER membership)
2) Owner/Manager invites member (STAFF or MANAGER)
3) Owner creates products (via legacy route for now), stocked in warehouses
4) Customer places order
5) Payment webhook arrives (Paystack/M-PESA), verified + idempotent
6) Org settlement computed (commission) and payout record created

## Idempotency and Safety
- Webhooks: deduped by raw-body SHA-256 (`accept_once` helper). Replays return 200 with no side effects.
- Stock decrement: `select_for_update` locks on orderitems & productstock; DB constraint prevents negatives.
- Payouts: `@idempotent('vendor:payout')` prevents double-exec with same key.

## OpenAPI Docs
- JSON: `/apis/v1/schema/?format=json`
- Swagger UI: `/apis/v1/docs/`

## Notes
- Legacy vendor endpoints remain as-is. New v1 endpoints are additive.
- VendorProfile.org is non-null after backfill migrations; `vendor_app` migrations include backfill steps.

