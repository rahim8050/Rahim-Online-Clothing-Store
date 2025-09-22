from __future__ import annotations

from urllib.parse import urljoin

from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.sites.requests import RequestSite
from django.db import DatabaseError, OperationalError, ProgrammingError

__all__ = ["current_domain", "absolute_url"]


def current_domain(request=None) -> str:
    """Return the canonical domain, falling back to request/env when Sites is unavailable."""

    try:
        return Site.objects.get_current().domain
    except (ProgrammingError, OperationalError, DatabaseError, Site.DoesNotExist):
        if request is not None:
            return RequestSite(request).domain
        return getattr(settings, "SITE_DOMAIN", "127.0.0.1:8000")


def absolute_url(path: str, request=None) -> str:
    """Build an absolute URL for *path* using the best context available."""

    if request is not None:
        return request.build_absolute_uri(path)

    scheme = getattr(
        settings, "SITE_SCHEME", "https" if getattr(settings, "IS_PROD", False) else "http"
    )
    domain = current_domain(None)
    base = f"{scheme}://{domain}".rstrip("/") + "/"
    return urljoin(base, path.lstrip("/"))
