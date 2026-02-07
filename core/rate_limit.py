from __future__ import annotations

from django.core.cache import cache


def get_client_ip(request) -> str:
    """Best-effort client IP (honors X-Forwarded-For if present)."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        # Use the first hop as the client IP
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "unknown"


def make_key(prefix: str, *parts: str) -> str:
    safe = [str(p).strip().lower() for p in parts if p is not None]
    return "rl:" + prefix + ":" + ":".join(safe)


def is_limited(key: str, limit: int) -> bool:
    try:
        return int(cache.get(key, 0)) >= int(limit)
    except Exception:
        return False


def hit(key: str, window_seconds: int) -> int:
    """Increment a rate-limit counter and return the current count."""
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window_seconds)
        return 1
    except Exception:
        try:
            current = int(cache.get(key, 0))
        except Exception:
            current = 0
        current += 1
        cache.set(key, current, timeout=window_seconds)
        return current


def reset(key: str) -> None:
    cache.delete(key)

