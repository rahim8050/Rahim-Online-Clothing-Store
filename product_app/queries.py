from django.db.models import Q

from users.utils import vendor_owner_ids_for


def shopable_products_q(user):
    if not getattr(user, "is_authenticated", False):
        return Q()
    forbidden_owner_ids = list(vendor_owner_ids_for(user))
    if not forbidden_owner_ids:
        return Q()
    return ~Q(owner_id__in=forbidden_owner_ids)
