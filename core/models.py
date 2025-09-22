from __future__ import annotations

from django.conf import settings
from django.db import models, transaction


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    owner_id = models.IntegerField(null=True, blank=True, db_index=True)
    action = models.CharField(max_length=64)
    target_type = models.CharField(max_length=64)
    target_id = models.CharField(max_length=64)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["owner_id", "created_at"]),
        ]


@transaction.atomic
def log_action(
    actor, owner_id: int | None, action: str, target_type: str, target_id, meta: dict | None = None
) -> AuditLog:
    return AuditLog.objects.create(
        actor=actor if getattr(actor, "pk", None) else None,
        owner_id=owner_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        meta=meta or {},
    )
