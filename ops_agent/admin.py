from django.contrib import admin
from .models import OpsTask

@admin.register(OpsTask)
class OpsTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "vendor_id", "kind", "status", "created_at")
    list_filter  = ("status", "kind")
    search_fields = ("payload",)
