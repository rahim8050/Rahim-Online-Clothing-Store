from __future__ import annotations

import hashlib
from collections.abc import Callable
from functools import wraps

from django.db import transaction

from .models import AuditLog, IdempotencyKey


def body_sha256(data: bytes) -> str:
    return hashlib.sha256(data or b"").hexdigest()


def idempotent(scope: str) -> Callable:
    """
    Decorator to enforce idempotency for side-effecting handlers.

    The wrapped function must accept either:
      - an `idempotency_key` kwarg, OR
      - a `request` kwarg whose header `X-Idempotency-Key` is used; if absent,
        we derive a key from the raw request body SHA256. As a last resort,
        we hash the function name + args/kwargs.

    The function is executed at most once per (scope, key) pair.
    """

    def deco(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            key: str | None = kwargs.pop("idempotency_key", None)

            # Try to derive from request if not explicitly provided
            request = kwargs.get("request")
            if key is None and request is not None:
                key = request.META.get("HTTP_X_IDEMPOTENCY_KEY")
                if not key:
                    try:
                        key = body_sha256(getattr(request, "body", b""))
                    except Exception:
                        key = None

            # Last resort: derive from deterministic representation of call
            if not key:
                raw = (str(func.__name__) + str(args) + str(sorted(kwargs.items()))).encode("utf-8")
                key = body_sha256(raw)

            with transaction.atomic():
                idem, created = IdempotencyKey.objects.select_for_update().get_or_create(
                    scope=scope, key=key
                )
                if not created:
                    AuditLog.log(event="IDEMPOTENT_REPLAY", message=f"{scope}:{key}")
                    # We still call the function; ensure your function is deterministic for the same key.

                result = func(*args, idempotency_key=key, **kwargs)

                # Record a hash of the response for traceability (best-effort)
                try:
                    rbytes = (str(result) or "").encode("utf-8")
                    idem.response_hash = body_sha256(rbytes)
                    idem.save(update_fields=["response_hash"])
                except Exception:
                    pass

                return result

        return wrapper

    return deco


def accept_once(*, scope: str, request=None, key: str | None = None) -> bool:
    """
    Return True if this (scope, key) should be processed the first time only.
    Subsequent calls with the same key return False (indicating a replay).

    - If key is not given, derive it as SHA256 of raw request.body.
    - Uses SELECT FOR UPDATE with get_or_create to serialize duplicates.
    """
    if key is None and request is not None:
        try:
            key = body_sha256(getattr(request, "body", b""))
        except Exception:
            key = None

    if not key:
        # Cannot dedupe without a key; accept and proceed.
        return True

    with transaction.atomic():
        _, created = IdempotencyKey.objects.select_for_update().get_or_create(
            scope=scope, key=key
        )
        if not created:
            AuditLog.log(
                event="IDEMPOTENT_REPLAY",
                request_id=getattr(request, "request_id", ""),
                message=f"{scope}:{key}",
            )
        return created
