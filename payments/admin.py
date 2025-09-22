from django.contrib import admin

from .models import AuditLog, Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "user", "gateway", "amount", "status", "created_at")
    search_fields = ("reference", "gateway_reference", "idempotency_key")
    list_filter = ("gateway", "status")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("event", "transaction", "order", "request_id", "created_at")
    search_fields = ("event", "request_id")
    list_filter = ("event",)
