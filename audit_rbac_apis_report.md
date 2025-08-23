# RBAC API Audit

## Endpoint summary

| Pattern | Name | View | Auth/roles |
| --- | --- | --- | --- |
| `vendor/products/` | vendor-products | `VendorProductsAPI` | `IsAuthenticated` + `InGroups` Vendor/Vendor Staff |
| `vendor/shopable-products/` | shopable-products | `ShopableProductsAPI` | `IsAuthenticatedOrReadOnly` |
| `driver/deliveries/` | driver-deliveries | `DriverDeliveriesAPI` | `IsAuthenticated` + Driver group |
| `driver/location/` | driver-location | `DriverLocationAPI` | `IsAuthenticated` + Driver group |
| `deliveries/<int:pk>/assign/` | delivery-assign | `DeliveryAssignAPI` | `IsAuthenticated` + Vendor/Vendor Staff |
| `deliveries/<int:pk>/unassign/` | delivery-unassign | `DeliveryUnassignAPI` | `IsAuthenticated` + Vendor/Vendor Staff |
| `deliveries/<int:pk>/accept/` | delivery-accept | `DeliveryAcceptAPI` | `IsAuthenticated` + Driver |
| `deliveries/<int:pk>/status/` | delivery-status | `DeliveryStatusAPI` | `IsAuthenticated` + Driver |
| `vendor/products/create/` | vendor-product-create | `VendorProductCreateAPI` | `IsAuthenticated` + Vendor/Vendor Staff |
| `vendor/apply/` | vendor-apply | `VendorApplyAPI` | `IsAuthenticated` |

## Role checks

* `users/views.py` – router `after_login` dispatches to vendor, driver and customer dashboards based on group membership.
* `apis/views.py` – class based APIs use `InGroups` permission to require appropriate roles.

## Gaps and Fixes

* Added `shopable_products_q` filter to exclude vendor/staff own listings.
* Introduced `ShopableProductsAPI` with `IsAuthenticatedOrReadOnly` and pagination.
* Added driver location stub with authentication and group check.
* Secured dashboard routing and added `/dashboard/` URL before category catch‑all.
* Reworked navbar to expose a unified dashboard link for authenticated users.
