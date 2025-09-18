# core/permissions.py
from __future__ import annotations

from typing import Any, Optional

from rest_framework.permissions import BasePermission
from users.constants import VENDOR, VENDOR_STAFF, DRIVER
from users.utils import in_groups as _in_groups


def _token_to_scopes(auth: Any) -> set[str]:
    """
    Normalize various auth representations into a set of scopes.
    Supports:
      - dict-like: {'scopes': [...]} or {'scope': 'a b c'} or {'permissions': [...]}
      - SimpleJWT token: has .payload dict
      - any object exposing .get(...) or .payload.get(...)
    """
    def _listify(x: Any) -> set[str]:
        if isinstance(x, (list, tuple, set)):
            return set(map(str, x))
        if isinstance(x, str):
            return set(x.split())
        return set()

    if auth is None:
        return set()

    # dict-like
    if hasattr(auth, "get"):
        scopes = auth.get("scopes")
        if scopes is not None:
            return _listify(scopes)
        # fallbacks some providers use
        perm = auth.get("permissions")
        if perm is not None:
            return _listify(perm)
        scope_str = auth.get("scope")
        return _listify(scope_str)

    # objects with .payload (e.g., SimpleJWT token)
    payload = getattr(auth, "payload", None)
   
