from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.core.validators import MinValueValidator
from django.db import models

from vendor_app.models import VendorOrg

Q2 = Decimal("0.01")


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    org = models.ForeignKey(
        VendorOrg, on_delete=models.PROTECT, related_name="invoices"
    )
    order = models.OneToOneField(
        "orders.Order", on_delete=models.PROTECT, related_name="invoice"
    )
    buyer_name = models.CharField(max_length=255)
    buyer_pin = models.CharField(max_length=12, blank=True, default="")
    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        default=Decimal("0.00"),
    )
    tax_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        default=Decimal("0.00"),
    )
    total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        default=Decimal("0.00"),
    )
    currency = models.CharField(max_length=10, default="KES")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    irn = models.CharField(max_length=64, blank=True, default="")
    issued_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")

    class Meta:
        indexes = [
            models.Index(
                fields=["org", "status", "issued_at"], name="invoice_org_status_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"Invoice #{self.pk} for order {self.order_id}"

    def compute_totals(self) -> tuple[Decimal, Decimal, Decimal]:
        lines = list(self.lines.all())
        sub = sum((line.line_total for line in lines), Decimal("0.00"))
        tax = sum((line.tax_total for line in lines), Decimal("0.00"))
        tot = (sub + tax).quantize(Q2, rounding=ROUND_HALF_UP)
        return (
            Decimal(sub).quantize(Q2, rounding=ROUND_HALF_UP),
            Decimal(tax).quantize(Q2, rounding=ROUND_HALF_UP),
            tot,
        )

    def save(self, *args, **kwargs):
        # Quantize stored totals
        self.subtotal = Decimal(self.subtotal or 0).quantize(Q2, rounding=ROUND_HALF_UP)
        self.tax_amount = Decimal(self.tax_amount or 0).quantize(
            Q2, rounding=ROUND_HALF_UP
        )
        self.total = Decimal(self.total or 0).quantize(Q2, rounding=ROUND_HALF_UP)
        if self.pk:
            sub, tax, tot = self.compute_totals()
            self.subtotal, self.tax_amount, self.total = sub, tax, tot
        return super().save(*args, **kwargs)


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    sku = models.CharField(max_length=64, blank=True, default="")
    name = models.CharField(max_length=255)
    qty = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.00"))],
        default=Decimal("0.00"),
    )
    line_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        default=Decimal("0.00"),
    )
    tax_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        default=Decimal("0.00"),
    )

    class Meta:
        indexes = [
            models.Index(fields=["invoice"], name="invoiceline_invoice_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} x {self.qty}"

    def compute(self) -> tuple[Decimal, Decimal]:
        lt = (Decimal(self.qty) * Decimal(self.unit_price)).quantize(
            Q2, rounding=ROUND_HALF_UP
        )
        tt = (lt * Decimal(self.tax_rate)).quantize(Q2, rounding=ROUND_HALF_UP)
        return lt, tt

    def save(self, *args, **kwargs):
        # Compute and quantize line totals
        self.line_total, self.tax_total = self.compute()
        return super().save(*args, **kwargs)
