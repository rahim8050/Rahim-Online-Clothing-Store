from __future__ import annotations

import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .enums import Gateway, TxnStatus, PaymentMethod


class Transaction(models.Model):
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="transactions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions")
    method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    gateway = models.CharField(max_length=20, choices=Gateway.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10)
    status = models.CharField(max_length=30, choices=TxnStatus.choices, default=TxnStatus.PENDING)
    idempotency_key = models.CharField(max_length=64, unique=True)
    reference = models.CharField(max_length=64, unique=True)
    gateway_reference = models.CharField(max_length=128, unique=True, null=True, blank=True)

    callback_received = models.BooleanField(default=False)
    signature_valid = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    raw_event = models.JSONField(default=dict, blank=True)

    refund_reference = models.CharField(max_length=128, null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["user"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["order"],
                condition=Q(status=TxnStatus.SUCCESS),
                name="unique_success_per_order",
            )
        ]

    def mark_success(self, gateway_reference: str | None = None):
        self.status = TxnStatus.SUCCESS
        if gateway_reference:
            self.gateway_reference = gateway_reference
        self.processed_at = timezone.now()
        self.save(update_fields=["status", "gateway_reference", "processed_at", "updated_at"])
        return self

    def mark_failed(self):
        self.status = TxnStatus.FAILED
        self.processed_at = timezone.now()
        self.save(update_fields=["status", "processed_at", "updated_at"])
        return self

    def mark_duplicate_success(self):
        self.status = TxnStatus.DUPLICATE_SUCCESS
        self.processed_at = timezone.now()
        self.save(update_fields=["status", "processed_at", "updated_at"])
        return self


class AuditLog(models.Model):
    event = models.CharField(max_length=64)
    transaction = models.ForeignKey(Transaction, null=True, blank=True, on_delete=models.CASCADE)
    order = models.ForeignKey("orders.Order", null=True, blank=True, on_delete=models.CASCADE)
    request_id = models.CharField(max_length=64, blank=True, default="")
    message = models.TextField(blank=True, default="")
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["event", "created_at"])]

    @classmethod
    def log(cls, *, event: str, transaction: Transaction | None = None, order=None, request_id: str = "", message: str = "", meta: dict | None = None):
        return cls.objects.create(
            event=event,
            transaction=transaction,
            order=order,
            request_id=request_id,
            message=message,
            meta=meta or {},
        )
