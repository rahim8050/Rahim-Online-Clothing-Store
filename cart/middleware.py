from django.contrib.auth import get_user
from django.utils.deprecation import MiddlewareMixin

from .guest import clear_cookie, get_signed_cookie
import logging
logger = logging.getLogger(__name__)


class ClearGuestCookieOnLoginMiddleware(MiddlewareMixin):
    """Clear guest cart cookie once a user is authenticated.

    This runs after authentication occurs and prevents stale cookies lingering.
    """

    def process_response(self, request, response):
        try:
            user = get_user(request)
            if getattr(user, "is_authenticated", False) and get_signed_cookie(request):
                clear_cookie(response)
        except Exception as e:
            logger.debug("clear_cookie failed: %s", e, exc_info=True)
        return response
