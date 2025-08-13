from django.db.models import Q

def shopable_products_q(user, product_model):
    """Return Q filtering out products owned by user or their active vendor bosses."""
    owner_field = None
    for name in ("owner", "vendor", "seller", "created_by", "user"):
        try:
            product_model._meta.get_field(name)
            owner_field = name
            break
        except Exception:
            continue
    if not owner_field or not getattr(user, "is_authenticated", False):
        return Q()

    from users.models import VendorStaff
    my_owner_ids = {user.id}
    staffed_for = VendorStaff.objects.filter(
        staff=user, is_active=True
    ).values_list("owner_id", flat=True)
    my_owner_ids.update(staffed_for)
    return ~Q(**{f"{owner_field}_id__in": list(my_owner_ids)})
