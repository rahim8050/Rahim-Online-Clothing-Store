# assistant/context_processors.py
from django.contrib.auth.models import AnonymousUser

def assistant_role(request):
    user = getattr(request, "user", AnonymousUser())

    def is_vendor(u):
        return (
            getattr(u, "is_vendor", False)
            or hasattr(u, "vendor")                # e.g., OneToOne vendor profile
            or hasattr(u, "vendorprofile")
            or u.groups.filter(name__in=["vendor", "vendors"]).exists()
        )

    def is_vendor_staff(u):
        return (
            getattr(u, "is_vendor_staff", False)
            or u.groups.filter(name__in=["vendor_staff", "vendor-staff"]).exists()
        )

    if not getattr(user, "is_authenticated", False):
        return {"assistant_role": "guest"}

    if is_vendor(user):
        role = "vendor"
    elif is_vendor_staff(user):
        role = "vendor_staff"
    elif getattr(user, "is_staff", False):
        role = "admin"
    else:
        role = "customer"

    return {"assistant_role": role}
