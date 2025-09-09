from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user

from .guest import clear_cookie, get_signed_cookie


class ClearGuestCookieOnLoginMiddleware(MiddlewareMixin):
    """Clear guest cart cookie once a user is authenticated.

    This runs after authentication occurs and prevents stale cookies lingering.
    """

    def process_response(self, request, response):
        try:
            user = get_user(request)
            if getattr(user, "is_authenticated", False) and get_signed_cookie(request):
                clear_cookie(response)
        except Exception:
            pass
        return response

