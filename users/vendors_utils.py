# users/vendor_utils.py
from django.apps import apps

def get_vendor_for_user(user):
    if not getattr(user, "is_authenticated", False):
        return None

    # direct links on user (adjust names to your schema)
    for attr in ("vendor", "vendor_profile", "owned_vendor"):
        v = getattr(user, attr, None)
        if v:
            return v

    # fallback to VendorStaff relation
    try:
        VendorStaff = apps.get_model("users", "VendorStaff")
        vs = VendorStaff.objects.select_related("vendor").filter(user=user).first()
        if vs and getattr(vs, "vendor", None):
            return vs.vendor
    except Exception:
        pass

    return None
