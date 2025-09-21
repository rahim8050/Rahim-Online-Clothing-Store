# users/vendor_utils.py
from django.contrib.auth import get_user_model

from .utils import resolve_vendor_owner_for


def get_vendor_for_user(user):
    """Return the acting vendor owner User instance for this user.
    Uses resolve_vendor_owner_for for a single source of truth.
    If the user cannot be resolved unambiguously, returns None."""
    if not getattr(user, "is_authenticated", False):
        return None
    try:
        owner_id = resolve_vendor_owner_for(user)
    except Exception:
        return None
    User = get_user_model()
    try:
        return User.objects.get(pk=owner_id)
    except User.DoesNotExist:
        return None
