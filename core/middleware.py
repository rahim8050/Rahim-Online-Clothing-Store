import uuid
from django.utils.deprecation import MiddlewareMixin
class PermissionsPolicyMiddleware:
    """Set restrictive Permissions-Policy headers."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Permissions-Policy"] = "geolocation=()"
        return response



class RequestIDMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.request_id = (
            request.META.get("HTTP_X_REQUEST_ID") or str(uuid.uuid4())
        )

    def process_response(self, request, response):
        rid = getattr(request, "request_id", None)
        if rid:
            response["X-Request-ID"] = rid
        return response
