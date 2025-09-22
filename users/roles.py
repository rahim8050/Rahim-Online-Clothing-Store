from django.contrib.auth.models import Group, Permission

ROLE_ADMIN = "Admin"
ROLE_CUSTOMER = "Customer"
ROLE_VENDOR = "Vendor"
ROLE_VENDOR_STAFF = "Vendor Staff"
ROLE_DRIVER = "Driver"

ROLE_DEFINITIONS = {
    ROLE_ADMIN: {"all_perms": True},
    ROLE_CUSTOMER: {"perms": []},
    ROLE_VENDOR: {
        "perms": [
            "add_product",
            "change_product",
            "delete_product",
            "view_product",
        ]
    },
    ROLE_VENDOR_STAFF: {
        "perms": [
            "change_product",
            "view_product",
        ]
    },
    ROLE_DRIVER: {"perms": ["view_order", "view_orderitem"]},
}


def sync_roles():
    """Create or update role groups and attach permissions."""
    for role, opts in ROLE_DEFINITIONS.items():
        group, _ = Group.objects.get_or_create(name=role)
        if opts.get("all_perms"):
            perms = Permission.objects.all()
        else:
            perms = Permission.objects.filter(codename__in=opts.get("perms", []))
        group.permissions.set(perms)
