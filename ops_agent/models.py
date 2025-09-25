# ──────────────────────────────────────────────────────────────────────────────
# ops_agent/models.py
# ──────────────────────────────────────────────────────────────────────────────
from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class OpsTask(models.Model):
    """Simple ops task created by the agent (e.g., restock request)."""

    KIND_CHOICES = (
        ("restock", "Restock"),
        ("investigate", "Investigate"),
    )
    STATUS_CHOICES = (
        ("open", "Open"),
        ("done", "Done"),
        ("dismissed", "Dismissed"),
    )

    vendor_id = models.PositiveIntegerField(db_index=True)
    kind = models.CharField(max_length=32, choices=KIND_CHOICES, default="restock")
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="open")
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["vendor_id", "status", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"OpsTask({self.vendor_id}, {self.kind}, {self.status})"
