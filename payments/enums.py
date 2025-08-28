from django.db import models


class Gateway(models.TextChoices):
    STRIPE = "stripe", "Stripe"
    PAYSTACK = "paystack", "Paystack"
    MPESA = "mpesa", "M-Pesa"


class TxnStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SUCCESS = "success", "Success"
    DUPLICATE_SUCCESS = "duplicate_success", "Duplicate Success"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"
    REFUNDED = "refunded", "Refunded"


class PaymentMethod(models.TextChoices):
    CARD = "card", "Card"
    MPESA = "mpesa", "M-Pesa"
