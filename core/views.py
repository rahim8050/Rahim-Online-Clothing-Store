from django.http import JsonResponse
from django.conf import settings

def _redis_ping():
    try:
        import redis  # type: ignore
        url = getattr(settings, "REDIS_URL", "")
        if not url:
            return {"ok": False, "error": "no_redis_config"}
        client = redis.Redis.from_url(url, ssl=getattr(settings, "REDIS_SSL", False))
        pong = client.ping()
        # Attempt default Celery queue depth (best effort)
        depth = None
        try:
            depth = client.llen("celery")
        except Exception:
            depth = None
        return {"ok": bool(pong), "queue_depth": depth}
    except Exception as e:  # pragma: no cover
        return {"ok": False, "error": str(e)}


def healthz(request):
    return JsonResponse({"status": "ok"})


def readyz(request):
    r = _redis_ping()
    # Celery reachability: if Redis ping ok, we assume broker reachable
    return JsonResponse({
        "status": "ok" if r.get("ok") else "degraded",
        "redis": r,
    }, status=200 if r.get("ok") else 503)
