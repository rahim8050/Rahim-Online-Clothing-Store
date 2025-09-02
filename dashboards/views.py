from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.apps import apps
from django.http import HttpResponseForbidden

from users.constants import VENDOR
from users.utils import is_vendor_or_staff, resolve_vendor_owner_for

def _vendor_id_for(user):
    """Return vendor_id for a Vendor or VendorStaff user; else None."""
    vid = getattr(user, "vendor_id", None)
    if vid:
        return vid
    if user.groups.filter(name=VENDOR).exists():
        return user.id
    try:
        VendorStaff = apps.get_model("users", "VendorStaff")
        return (
            VendorStaff.objects
            .filter(staff=user, is_active=True)
            .values_list("owner_id", flat=True)
            .first()
        )
    except Exception:
        return None

@login_required
def vendor_dashboard(request):
    u = request.user
    if not is_vendor_or_staff(u):
        return HttpResponseForbidden("Insufficient role")

    Product   = apps.get_model("product_app", "Product")
    OrderItem = apps.get_model("orders", "OrderItem")

    vendor_id = _vendor_id_for(u)
    if not vendor_id:
        # No vendor link yet; render empty with a hint
        return render(request, "dashboards/vendor.html", {
            "stats": {"products_total": 0, "active_products": 0, "order_items_total": 0},
            "products": [], "order_items": [],
            "note": "Your account is not linked to a vendor profile yet."
        })

    # Stats (cheap counts)
    products_qs = Product.objects.filter(owner_id=vendor_id)
    stats = {
        "products_total": products_qs.count(),
        "active_products": products_qs.filter(available=True).count(),
        "order_items_total": OrderItem.objects.filter(product__owner_id=vendor_id).count(),
    }

    # Lists (limited + narrow field selection)
    products = (
        products_qs
        .only("id", "name", "price", "available")
        .order_by("-id")[:25]
    )

    order_items = (
        OrderItem.objects
        .filter(product__owner_id=vendor_id)
        .select_related("order", "product")
        .only("id", "quantity", "price", "order__id", "product__name")
        .order_by("-id")[:25]
    )

    return render(request, "dashboards/vendor.html", {
        "stats": stats,
        "products": products,
        "order_items": order_items,
        "note": "",
    })


@login_required
def vendor_live(request):
    """Simple live board that polls vendor deliveries API and renders a table.
    Requires vendor or staff role. Owner context resolved in the client via owner_id param if needed.
    """
    u = request.user
    if not is_vendor_or_staff(u):
        return HttpResponseForbidden("Insufficient role")
    return render(request, "dashboards/vendor_live.html", {})
