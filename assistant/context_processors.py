# assistant/context_processors.py
from django.contrib.auth.models import Group

def _has(u, name: str) -> bool:
    """Robust role detector: supports user.role, boolean flags, and Django groups."""
    name_l = name.lower()
    return (
        getattr(u, "role", "").lower() == name_l
        or bool(getattr(u, f"is_{name_l}", False))
        or u.groups.filter(name__iexact=name_l).exists()
    )

def assistant_role(request):
    u = request.user
    if not u.is_authenticated:
        role = "guest"
    elif getattr(u, "is_superuser", False) or getattr(u, "is_staff", False):
        role = "admin"
    elif _has(u, "vendor"):
        role = "vendor"
    elif _has(u, "vendor_staff"):
        role = "vendor_staff"
    elif _has(u, "driver"):
        role = "driver"
    else:
        role = "customer"

    return {
        "assistant_role": role,
        "user_is_vendor": role == "vendor",
        "user_is_vendor_staff": role == "vendor_staff",
        "user_is_driver": role == "driver",
    }
