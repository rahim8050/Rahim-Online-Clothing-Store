from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings

from core import metrics
from .kpi import aggregate_kpis_daily
from .models import VendorOrg

logger = logging.getLogger(__name__)


@shared_task
def aggregate_kpis_daily_all() -> int:
    if not getattr(settings, "KPIS_ENABLED", False):
        logger.info("kpi.skip", extra={"reason": "feature_disabled"})
        return 0

    count = 0
    for org_id in VendorOrg.objects.values_list("id", flat=True):
        try:
            aggregate_kpis_daily(org_id)
            metrics.inc("kpi_jobs_success", org_id=org_id)
            count += 1
        except Exception:  # pragma: no cover
            logger.exception("kpi.error", extra={"org_id": org_id})
            metrics.inc("kpi_jobs_fail", org_id=org_id)
    return count
