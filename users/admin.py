
"""Admin configuration for users app."""

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.core.mail import send_mail


# users/admin.py
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.core.mail import send_mail
from django.utils import timezone
from django.contrib.admin.helpers import ActionForm  # ✅ import this

from .models import CustomUser, VendorApplication, VendorStaff
from users.services import deactivate_staff as deactivate_vendor_staff


admin.site.register(CustomUser, UserAdmin)


class VendorApplicationActionForm(forms.Form):
    """Extra field for reject action."""


class VendorApplicationActionForm(ActionForm):  # ✅ subclass ActionForm (has `action`)
    """Extra field for reject action."""

    note = forms.CharField(
        required=False,
        label="Rejection note",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Optional note stored on each rejected application.",
    )


@admin.register(VendorApplication)
class VendorApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "company_name",
        "status",
        "created_at",
        "decided_by",
        "decided_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "user__email", "company_name")
    autocomplete_fields = ("user",)
    date_hierarchy = "created_at"


    action_form = VendorApplicationActionForm

    action_form = VendorApplicationActionForm  # ✅ keep using our subclass

    actions = ("approve_selected", "reject_selected")

    @admin.action(description="Approve selected applications")
    def approve_selected(self, request, queryset):
        qs = queryset.filter(status=VendorApplication.Status.PENDING).select_related("user")
        approved = 0
        for app in qs:
            app.approve(request.user)
            send_mail(
                "Vendor application approved",
                f"Your vendor application for {app.company_name} has been approved.",
                settings.DEFAULT_FROM_EMAIL,
                [app.user.email],
                fail_silently=True,
            )
            approved += 1
        skipped = queryset.count() - approved
        if approved:
            self.message_user(request, f"Approved {approved} application(s).", level=messages.SUCCESS)
        if skipped:
            self.message_user(request, f"Skipped {skipped} non-pending application(s).", level=messages.WARNING)

    @admin.action(description="Reject selected applications")
    def reject_selected(self, request, queryset):
        note = request.POST.get("note") or "Rejected via admin."
        qs = queryset.filter(status=VendorApplication.Status.PENDING).select_related("user")
        rejected = 0
        for app in qs:
            app.reject(request.user, note=note)
            send_mail(
                "Vendor application rejected",
                note,
                settings.DEFAULT_FROM_EMAIL,
                [app.user.email],
                fail_silently=True,
            )
            rejected += 1
        skipped = queryset.count() - rejected
        if rejected:
            self.message_user(request, f"Rejected {rejected} application(s).", level=messages.WARNING)
        if skipped:
            self.message_user(request, f"Skipped {skipped} non-pending application(s).", level=messages.INFO)


@admin.register(VendorStaff)
class VendorStaffAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "staff", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("owner__username", "owner__email", "staff__username", "staff__email")
    autocomplete_fields = ("owner", "staff")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not obj.is_active:
            deactivate_vendor_staff(obj)
