from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from vendor_app.models import VendorOrg
from .enums import Gateway, PaymentMethod, TxnStatus


class IdempotencyKey(models.Model):
    """Generic idempotency key storage.

    Use to dedupe side-effecting operations across retries (e.g., payouts).
    Keys are unique per scope to allow reuse in different domains.
    """
    scope = models.CharField(max_length=64, db_index=True)
    key = models.CharField(max_length=128)
    response_hash = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["scope", "key"], name="uniq_idem_scope_key"),
        ]
        indexes = [
            models.Index(fields=["created_at"], name="idem_created_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.scope}:{self.key}"


class Transaction(models.Model):
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="transactions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions"
    )
    vendor_org = models.ForeignKey(
        VendorOrg, null=True, blank=True, on_delete=models.SET_NULL, related_name="transactions"
    )

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

    # Settlement breakdown
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fees_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_to_vendor = models.DecimalField(max_digits=12, decimal_places=2, default=0)

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
            # Only one SUCCESS per order (duplicates must refund or be marked duplicate)
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
    def log(
        cls,
        *,
        event: str,
        transaction: Transaction | None = None,
        order=None,
        request_id: str = "",
        message: str = "",
        meta: dict | None = None,
    ):
        return cls.objects.create(
            event=event,
            transaction=transaction,
            order=order,
            request_id=request_id,
            message=message,
            meta=meta or {},
        )


class NotificationEvent(models.Model):
    event_key = models.CharField(max_length=128, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payment_notifications",
    )
    channel = models.CharField(max_length=24, default="email")  # e.g. email | sms | both
    payload = models.JSONField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payments_notification_event"
        verbose_name = "Notification event"
        verbose_name_plural = "Notification events"

    def __str__(self):
        return self.event_key


class Refund(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    transaction = models.ForeignKey(
        "payments.Transaction", on_delete=models.CASCADE, related_name="refunds"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    gateway = models.CharField(max_length=32)  # "paystack" | "stripe" | "mpesa"
    reason = models.CharField(max_length=64, default="duplicate")
    refund_reference = models.CharField(max_length=128, null=True, blank=True)  # provider refund id
    raw_response = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payments_refund"

    def __str__(self):
        return f"{self.transaction.reference} -> {self.status}"


class PaymentEvent(models.Model):
    provider = models.CharField(max_length=24)
    reference = models.CharField(max_length=128, db_index=True)
    vendor_org = models.ForeignKey(
        VendorOrg, null=True, blank=True, on_delete=models.SET_NULL, related_name="payment_events"
    )
    body_sha256 = models.CharField(max_length=64, unique=True)
    body = models.JSONField(null=True, blank=True)
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fees_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_to_vendor = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["reference", "created_at"])]


class Payout(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        QUEUED = "queued", "Queued"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    vendor_org = models.ForeignKey(VendorOrg, on_delete=models.CASCADE, related_name="payouts")
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name="payout")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="KES")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)
