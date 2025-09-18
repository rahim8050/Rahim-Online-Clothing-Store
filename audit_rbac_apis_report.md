# RBAC API Audit — Clean Merge & Permission Matrix

This document resolves merge markers, unifies naming, and codifies the permission rules for your role‑based APIs. It also includes ready‑to‑drop DRF permission classes and tests.

> **Prefix:** All patterns below assume they are mounted under `/apis/v1/` (e.g., `/apis/v1/vendor/products/`). Adjust the root include if your project uses a different prefix.

---

## Endpoint Summary (Clean)

| Pattern                         | Name                         | View                      | Auth / Roles                                                                               |
| ------------------------------- | ---------------------------- | ------------------------- | ------------------------------------------------------------------------------------------ |
| `vendor/products/`              | `vendor-products`            | `VendorProductsAPI`       | `IsAuthenticated` ∧ `IsVendorOrVendorStaff`                                                |
| `vendor/products/create/`       | `vendor-product-create`      | `VendorProductCreateAPI`  | `IsAuthenticated` ∧ `IsVendorOrVendorStaff`                                                |
| `vendor/shopable-products/`     | `shopable-products`          | `ShopableProductsAPI`     | `IsAuthenticatedOrReadOnly` (GET open; server prevents self‑purchase)                      |
| `vendor/owners/`                | `vendor-owners`              | `VendorOwnersAPI`         | `IsAuthenticated` ∧ `IsVendorOwner`                                                        |
| `vendor/products/import-csv/`   | `vendor-products-import-csv` | `VendorProductsImportCSV` | `IsAuthenticated` ∧ ( `IsVendorOwner` ∨ (`IsVendorStaff` ∧ `HasVendorScope('catalog')`) )  |
| `vendor/products/export-csv/`   | `vendor-products-export-csv` | `VendorProductsExportCSV` | `IsAuthenticated` ∧ ( `IsVendorOwner` ∨ (`IsVendorStaff` ∧ `HasVendorScope('catalog')`) )  |
| `driver/deliveries/`            | `driver-deliveries`          | `DriverDeliveriesAPI`     | `IsAuthenticated` ∧ `IsDriver`                                                             |
| `driver/location/`              | `driver-location`            | `DriverLocationAPI`       | `IsAuthenticated` ∧ `IsDriver`                                                             |
| `deliveries/<int:pk>/assign/`   | `delivery-assign`            | `DeliveryAssignAPI`       | `IsAuthenticated` ∧ ( `IsVendorOwner` ∨ (`IsVendorStaff` ∧ `HasVendorScope('delivery')`) ) |
| `deliveries/<int:pk>/unassign/` | `delivery-unassign`          | `DeliveryUnassignAPI`     | `IsAuthenticated` ∧ ( `IsVendorOwner` ∨ (`IsVendorStaff` ∧ `HasVendorScope('delivery')`) ) |
| `deliveries/<int:pk>/accept/`   | `delivery-accept`            | `DeliveryAcceptAPI`       | `IsAuthenticated` ∧ `IsDriver`                                                             |
| `deliveries/<int:pk>/status/`   | `DeliveryStatusAPI`          | `delivery-status`         | `IsAuthenticated` ∧ `IsDriver`                                                             |
| `vendor/apply/`                 | `vendor-apply`               | `VendorApplyAPI`          | `IsAuthenticated` (non‑vendor only)                                                        |

---

## Role Checks (Unified)

* **Groups provisioned**: `Admin`, `Customer`, `Vendor`, `Vendor Staff`, `Driver`. Use `python manage.py sync_roles` idempotently.
* **Vendor membership model**: `VendorStaff` (`user`, `vendor`, `owner: bool`, `active: bool`, `scopes: JSON`) powers fine‑grained checks.
* **Scopes**: strings like `"catalog"`, `"delivery"` in `VendorStaff.scopes` for staff. **Owners automatically pass** scope checks.
* **Dashboards**: `users.views.after_login` routes to vendor/driver/customer dashboards by group membership.

---

## Permissions — Drop‑in Classes (`apis/permissions.py`)

```python
from __future__ import annotations
from typing import Iterable
from django.contrib.auth.models import Group
from rest_framework.permissions import BasePermission, SAFE_METHODS

VENDOR_GROUP = "Vendor"
VENDOR_STAFF_GROUP = "Vendor Staff"
DRIVER_GROUP = "Driver"

class IsAuthenticatedOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or (request.user and request.user.is_authenticated)

class InAnyGroup(BasePermission):
    groups: Iterable[str] = ()
    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if u.is_superuser:
            return True
        names = set(g.name for g in u.groups.all())
        return any(g in names for g in self.groups)

class IsVendorOrVendorStaff(InAnyGroup):
    groups = (VENDOR_GROUP, VENDOR_STAFF_GROUP)

class IsVendorStaff(InAnyGroup):
    groups = (VENDOR_STAFF_GROUP,)

class IsDriver(InAnyGroup):
    groups = (DRIVER_GROUP,)

# Assumes you have a VendorStaff model linked to user
class IsVendorOwner(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if getattr(u, "is_superuser", False):
            return True
        # owner if any active membership is owner
        return getattr(u, "vendorstaff_set", None) and u.vendorstaff_set.filter(active=True, owner=True).exists()

class HasVendorScope(BasePermission):
    scope_name: str
    def __init__(self, scope_name: str = ""):
        self.scope_name = scope_name
    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if getattr(u, "is_superuser", False):
            return True
        # Owners always pass
        qs = getattr(u, "vendorstaff_set", None)
        if not qs:
            return False
        if qs.filter(active=True, owner=True).exists():
            return True
        # Staff must have scope
        return qs.filter(active=True, owner=False, scopes__contains=[self.scope_name]).exists()
```

> These classes avoid hard‑coding a particular `VendorStaff` app path by using the reverse relation `user.vendorstaff_set`. If your relation name differs, adjust accordingly.

---

## Views — Applying the Policy (examples)

```python
# apis/views_vendor.py
from rest_framework.generics import ListAPIView, CreateAPIView
from .permissions import (
    IsAuthenticatedOrReadOnly, IsVendorOrVendorStaff, IsVendorOwner, IsVendorStaff, HasVendorScope
)

class VendorProductsAPI(ListAPIView):
    permission_classes = [IsVendorOrVendorStaff]
    # queryset / serializer_class ...

class VendorProductCreateAPI(CreateAPIView):
    permission_classes = [IsVendorOrVendorStaff]

class ShopableProductsAPI(ListAPIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    # ensure server‑side filter excludes vendor/staff own listings

class VendorProductsImportCSV(CreateAPIView):
    # Owners pass; staff require `catalog` scope
    def get_permissions(self):
        return [IsVendorOwner() or (IsVendorStaff() and HasVendorScope("catalog"))]
        # Alternatively implement a CombinedPermission to allow OR semantics cleanly
```

**OR semantics helper (cleaner):**

```python
# apis/permissions_combined.py
from rest_framework.permissions import BasePermission

class AnyOf(BasePermission):
    def __init__(self, *perms: BasePermission):
        self.perms = perms
    def has_permission(self, request, view):
        return any(p.has_permission(request, view) for p in self.perms)

class AllOf(BasePermission):
    def __init__(self, *perms: BasePermission):
        self.perms = perms
    def has_permission(self, request, view):
        return all(p.has_permission(request, view) for p in self.perms)
```

Usage:

```python
permission_classes = [AllOf(IsVendorStaff(), HasVendorScope("catalog"))]
# or
permission_classes = [AnyOf(IsVendorOwner(), AllOf(IsVendorStaff(), HasVendorScope("catalog")))]
```

---

## URL Wiring (excerpt)

```python
# apis/urls.py
from django.urls import path
from . import views_vendor, views_driver, views_delivery

urlpatterns = [
    path("vendor/products/", views_vendor.VendorProductsAPI.as_view(), name="vendor-products"),
    path("vendor/products/create/", views_vendor.VendorProductCreateAPI.as_view(), name="vendor-product-create"),
    path("vendor/shopable-products/", views_vendor.ShopableProductsAPI.as_view(), name="shopable-products"),
    path("vendor/owners/", views_vendor.VendorOwnersAPI.as_view(), name="vendor-owners"),
    path("vendor/products/import-csv/", views_vendor.VendorProductsImportCSV.as_view(), name="vendor-products-import-csv"),
    path("vendor/products/export-csv/", views_vendor.VendorProductsExportCSV.as_view(), name="vendor-products-export-csv"),

    path("driver/deliveries/", views_driver.DriverDeliveriesAPI.as_view(), name="driver-deliveries"),
    path("driver/location/", views_driver.DriverLocationAPI.as_view(), name="driver-location"),

    path("deliveries/<int:pk>/assign/", views_delivery.DeliveryAssignAPI.as_view(), name="delivery-assign"),
    path("deliveries/<int:pk>/unassign/", views_delivery.DeliveryUnassignAPI.as_view(), name="delivery-unassign"),
    path("deliveries/<int:pk>/accept/", views_delivery.DeliveryAcceptAPI.as_view(), name="delivery-accept"),
    path("deliveries/<int:pk>/status/", views_delivery.DeliveryStatusAPI.as_view(), name="delivery-status"),

    path("vendor/apply/", views_vendor.VendorApplyAPI.as_view(), name="vendor-apply"),
]
```

---

## Server‑Side Safeguards (catalog / purchase)

* **`shopable_products_q`**: filter excludes listings where the requesting user is the vendor or staff of the vendor.
* **Self‑purchase prevention**: enforce again in the order/create view (defense in depth).
* **Audit Trail**: Use `core.AuditLog` to capture product create/update, staff invite/accept/remove/deactivate, and delivery assign/unassign.

Pseudo‑filter:

```python
from django.db.models import Q

def shopable_products_q(user):
    if not (user and user.is_authenticated):
        return Q()
    # Exclude products where user owns the vendor or is active staff for that vendor
    vendor_ids = list(getattr(user, "vendorstaff_set", []).filter(active=True).values_list("vendor_id", flat=True))
    if not vendor_ids:
        return Q()
    return ~Q(vendor_id__in=vendor_ids)
```

---

## Tests — Permission Matrix (`tests/test_rbac_permissions.py`)

```python
import pytest
from rest_framework.test import APIClient
from django.contrib.auth.models import User, Group

@pytest.fixture
def client():
    return APIClient()

@pytest.fixture
def mkuser(db):
    def _mk(username, groups=(), superuser=False):
        u = User.objects.create_user(username, password="pass")
        if superuser:
            u.is_superuser = True
            u.save(update_fields=["is_superuser"])
        for g in groups:
            grp, _ = Group.objects.get_or_create(name=g)
            u.groups.add(grp)
        return u
    return _mk

@pytest.mark.parametrize("url, method, groups, expected", [
    ("/apis/v1/vendor/products/", "get", ["Vendor"], 200),
    ("/apis/v1/vendor/products/", "get", ["Vendor Staff"], 200),
    ("/apis/v1/vendor/products/", "get", ["Customer"], 403),
    ("/apis/v1/vendor/shopable-products/", "get", [], 200),  # read‑only open
    ("/apis/v1/driver/deliveries/", "get", ["Driver"], 200),
    ("/apis/v1/driver/deliveries/", "get", ["Vendor"], 403),
])
 def test_matrix(client, mkuser, url, method, groups, expected):
    u = mkuser("u", groups=groups)
    client.login(username="u", password="pass")
    resp = getattr(client, method)(url)
    assert resp.status_code == expected
```

Add separate tests for `HasVendorScope('catalog')` and delivery scope logic by seeding `VendorStaff` with `scopes=["catalog"]` or `scopes=["delivery"]`.

---

## Operational Notes

* **Group sync**: When a user becomes an active vendor staff, add them to `Vendor Staff`. On deactivation of their last membership, remove the group.
* **Owner bypass**: Owners pass all vendor staff gates; keep this invariant consistent through code and tests.
* **Admin bypass**: `is_superuser` passes all checks.
* **404 over 403**: For object‑scoped views, prefer 404 when the object belongs to a different vendor to avoid information leaks.

---

**End of document.**
