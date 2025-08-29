# core/middleware.py
import uuid
from django.conf import settings

# Allowed origins for local development (both HTTP and HTTPS)
DEV_ORIGINS = (
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "https://127.0.0.1:8000",
    "https://localhost:8000",
)


class RequestIDMiddleware:
    """Attach a request id and echo it back in the response."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.META.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex
        request.request_id = rid
        resp = self.get_response(request)
        resp.headers["X-Request-ID"] = rid
        return resp


class PermissionsPolicyMiddleware:
    """
    Set/override ONLY the geolocation directive.

    - DEBUG=True  -> allow geolocation for self + local dev origins
    - DEBUG=False -> disable geolocation (adjust to your prod origins if needed)
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resp = self.get_response(request)

        # start with existing header and strip any existing geolocation=...
        current = resp.headers.get("Permissions-Policy", "")
        parts = [p.strip() for p in current.split(",") if p.strip()]
        parts = [p for p in parts if not p.lower().startswith("geolocation=")]

        if settings.DEBUG:
            allow = ' '.join(f'"{o}"' for o in DEV_ORIGINS)
            parts.append(f'geolocation=(self {allow})')
        else:
            parts.append('geolocation=()')

        resp.headers["Permissions-Policy"] = ", ".join(parts)
        return resp
