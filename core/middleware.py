# core/middleware.py
from __future__ import annotations

import uuid
from django.conf import settings

# Allowed origins for local development (both HTTP and HTTPS)
DEV_ORIGINS = (
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "https://127.0.0.1:8000",
    "https://localhost:8000",
)


def _set_header(resp, name: str, value: str) -> None:
    """
    Set a response header compatibly across Django versions.
    Django 3.2+ has resp.headers; older uses mapping interface.
    """
    try:
        resp.headers[name] = value
    except AttributeError:
        resp[name] = value


def _get_header(resp, name: str, default: str = "") -> str:
    """
    Get a response header safely across Django versions.
    """
    try:
        return resp.headers.get(name, default)
    except AttributeError:
        # Older Django: has_header + mapping access
        return resp[name] if hasattr(resp, "has_header") and resp.has_header(name) else default


class RequestIDMiddleware:
    """Attach a request ID and echo it back in the response as X-Request-ID."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.META.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex
        request.request_id = rid
        resp = self.get_response(request)
        _set_header(resp, "X-Request-ID", rid)
        return resp


class PermissionsPolicyMiddleware:
    """
    Set/override ONLY the geolocation directive in the Permissions-Policy header.

    - DEBUG=True  -> allow geolocation for self + local dev origins
    - DEBUG=False -> disable geolocation (tight by default; adjust for prod as needed)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resp = self.get_response(request)

        # Start with existing header and strip any existing geolocation=...
        current = _get_header(resp, "Permissions-Policy", "")
        parts = [p.strip() for p in current.split(",") if p.strip()]
        parts = [p for p in parts if not p.lower().startswith("geolocation=")]

        if settings.DEBUG:
            # Quote origins per spec: geolocation=(self "https://example.com" ...)
            allow = " ".join(f'"{o}"' for o in DEV_ORIGINS)
            parts.append(f"geolocation=(self {allow})")
        else:
            # Lock it down in prod unless explicitly allowed
            parts.append("geolocation=()")

        _set_header(resp, "Permissions-Policy", ", ".join(parts))
        return resp
