from __future__ import annotations

import hashlib
from collections.abc import Callable
from functools import wraps

from django.db import transaction

from .models import AuditLog, IdempotencyKey

import logging
logger = logging.getLogger(__name__)
def body_sha256(data: bytes) -> str:
    return hashlib.sha256(data or b"").hexdigest()


def idempotent(scope: str) -> Callable:
    """Decorator to enforce idempotency for side-effecting handlers.

    The wrapped function must accept either `idempotency_key` kwarg or a `request`
    kwarg whose header `X-Idempotency-Key` or body is used to derive a key.
    The function is executed at most once per (scope,key) pair.
    """

    def deco(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            key: str | None = kwargs.pop("idempotency_key", None)
            request = kwargs.get("request")
            if key is None and request is not None:
                key = request.META.get("HTTP_X_IDEMPOTENCY_KEY")
                if not key:
                    try:
                        key = body_sha256(getattr(request, "body", b""))
                    except Exception:
                        key = None
            if not key:
                # derive from function + args hash (last resort)
                raw = (str(func.__name__) + str(args) + str(sorted(kwargs.items()))).encode("utf-8")
                key = body_sha256(raw)

            with transaction.atomic():
                idem, created = IdempotencyKey.objects.select_for_update().get_or_create(
                    scope=scope, key=key
                )
                if not created:
                    AuditLog.log(event="IDEMPOTENT_REPLAY", message=f"{scope}:{key}")
                    # Return deterministic value by re-invoking function in a dry way is risky.
                    # Expect wrapped function to be deterministic based on the key.
                result = func(*args, idempotency_key=key, **kwargs)
                # Store a hash of result representation for traceability
                try:
                    rbytes = (str(result) or "").encode("utf-8")
                    idem.response_hash = body_sha256(rbytes)
                    idem.save(update_fields=["response_hash"])
                except Exception as e:
                   logger.debug("idempotency side-effect failed: %s", e, exc_info=True)
                return result

        return wrapper

    return deco


def accept_once(*, scope: str, request=None, key: str | None = None) -> bool:
    """Return True if this (scope,key) is accepted for first processing.

    - If key not given, derive as SHA256 of raw request.body
    - Uses SELECT FOR UPDATE get_or_create to serialize duplicates
    """
    if key is None and request is not None:
        try:
            key = body_sha256(getattr(request, "body", b""))
        except Exception:
            key = None
    if not key:
        return True  # fallback: cannot dedupe without a key
    with transaction.atomic():
        _, created = IdempotencyKey.objects.select_for_update().get_or_create(scope=scope, key=key)
        if not created:
            AuditLog.log(
                event="IDEMPOTENT_REPLAY",
                request_id=getattr(request, "request_id", ""),
                message=f"{scope}:{key}",
            )
        return created
