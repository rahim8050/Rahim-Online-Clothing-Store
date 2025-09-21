from django.contrib import admin

from .models import VendorKPI, VendorMember, VendorOrg, VendorOrgAuditLog, VendorProfile


@admin.register(VendorOrg)
class VendorOrgAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "owner", "is_active", "tax_status", "created_at")
    list_filter = ("is_active", "tax_status")
    search_fields = ("name", "slug", "owner__email", "owner__username", "kra_pin")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(VendorMember)
class VendorMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "org", "user", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("org__name", "org__slug", "user__email", "user__username")


@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "org", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("user__email", "user__username", "org__slug")


@admin.register(VendorOrgAuditLog)
class VendorOrgAuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "org", "field", "actor", "created_at")
    list_filter = ("field",)
    search_fields = ("org__slug", "actor__email", "actor__username", "field")


@admin.register(VendorKPI)
class VendorKPIAdmin(admin.ModelAdmin):
    list_display = (
        "org",
        "window",
        "period_start",
        "gross_revenue",
        "net_revenue",
        "orders",
        "refunds",
        "success_rate",
    )
    list_filter = ("window", "org")
    search_fields = ("org__slug",)
