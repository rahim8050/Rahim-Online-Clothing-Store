from django.http import JsonResponse
from django.db import connection


def healthz(request):
    return JsonResponse({"status": "ok"})


def readyz(request):
    """Lightweight readiness probe: verifies DB connectivity.
    Avoids migrations or table access; runs a trivial SELECT 1.
    """
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return JsonResponse({"status": "ready"})
    except Exception as e:
        return JsonResponse({"status": "degraded", "error": str(e)}, status=503)
