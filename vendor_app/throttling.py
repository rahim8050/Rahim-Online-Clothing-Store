from __future__ import annotations

from rest_framework.throttling import ScopedRateThrottle


class VendorOrgScopedRateThrottle(ScopedRateThrottle):
    """Throttle keyed by user + org id to avoid cross-org interference.

    Configure rates via DRF DEFAULT_THROTTLE_RATES, e.g.:
    {
      'vendor.org': '100/min'
    }
    """

    scope = "vendor.org"

    def get_cache_key(self, request, view):
        base = super().get_cache_key(request, view)
        if not base:
            return None
        org_id = None
        if hasattr(view, "kwargs"):
            org_id = view.kwargs.get("org_id") or view.kwargs.get("pk")
        if org_id is None and hasattr(request, "query_params"):
            org_id = request.query_params.get("org_id") or request.query_params.get(
                "org"
            )
        return f"{base}:org:{org_id}" if org_id else base
