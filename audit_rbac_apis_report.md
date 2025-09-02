# RBAC API Audit

## Endpoint summary

| Pattern | Name | View | Auth/roles |
| --- | --- | --- | --- |
| `vendor/products/` | vendor-products | `VendorProductsAPI` | `IsAuthenticated` + `IsVendorOrVendorStaff` |
| `vendor/shopable-products/` | shopable-products | `ShopableProductsAPI` | `IsAuthenticatedOrReadOnly` |
| `driver/deliveries/` | driver-deliveries | `DriverDeliveriesAPI` | `IsAuthenticated` + Driver group |
| `driver/location/` | driver-location | `DriverLocationAPI` | `IsAuthenticated` + Driver group |
| `deliveries/<int:pk>/assign/` | delivery-assign | `DeliveryAssignAPI` | `IsAuthenticated` + `IsVendorOrVendorStaff` |
| `deliveries/<int:pk>/unassign/` | delivery-unassign | `DeliveryUnassignAPI` | `IsAuthenticated` + `IsVendorOrVendorStaff` |
| `deliveries/<int:pk>/accept/` | delivery-accept | `DeliveryAcceptAPI` | `IsAuthenticated` + Driver |
| `deliveries/<int:pk>/status/` | delivery-status | `DeliveryStatusAPI` | `IsAuthenticated` + Driver |
| `vendor/products/create/` | vendor-product-create | `VendorProductCreateAPI` | `IsAuthenticated` + `IsVendorOrVendorStaff` |
| `vendor/apply/` | vendor-apply | `VendorApplyAPI` | `IsAuthenticated` |
| `vendor/owners/` | vendor-owners | `VendorOwnersAPI` | `IsAuthenticated` + `IsVendorOrVendorStaff` |
| `vendor/products/import-csv/` | vendor-products-import-csv | `VendorProductsImportCSV` | `IsAuthenticated` + `HasVendorScope('catalog')` |
| `vendor/products/export-csv/` | vendor-products-export-csv | `VendorProductsExportCSV` | `IsAuthenticated` + `HasVendorScope('catalog')` |

## Role checks

* `users/views.py` – router `after_login` dispatches to vendor, driver and customer dashboards based on group membership.
* `apis/views.py` – vendor endpoints now use `IsVendorOrVendorStaff`. Staff mutations are `IsVendorOwner`.
* New `HasVendorScope` lets owners pass automatically and staff require explicit JSON `scopes` on membership.

## Gaps and Fixes

* Vendor endpoints unified on `IsVendorOrVendorStaff`.
* Staff mutations (invite/create/remove/deactivate) require `IsVendorOwner` (admin bypass).
* Scopes: `VendorStaff.scopes` JSONField powers fine-grained gates (`catalog`, `delivery`).
* Group sync: accepting/activating staff adds to `Vendor Staff`; deactivating last membership removes from group.
* `shopable_products_q` prevents self-purchase and staff purchase of owner listings.
* `ShopableProductsAPI` provides paginated public catalog (read-only for guests).
* Audit trail: `core.AuditLog` records product create, staff invite/accept/remove/deactivate, delivery assign/unassign.
