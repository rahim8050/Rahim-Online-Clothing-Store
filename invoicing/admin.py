from django.contrib import admin

from .models import Invoice, InvoiceLine


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "org",
        "order",
        "buyer_name",
        "subtotal",
        "tax_amount",
        "total",
        "status",
        "issued_at",
    )
    list_filter = ("status", "org")
    search_fields = ("buyer_name", "order__id", "irn")
    inlines = [InvoiceLineInline]
