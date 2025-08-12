from django.contrib import admin
from .models import CustomUser
from django.contrib.auth.admin import UserAdmin
from django.contrib import admin, messages
from django import forms
from .models import VendorApplication, VendorStaff


admin.site.register(CustomUser, UserAdmin)






class VendorApplicationActionForm(forms.Form):
    rejection_reason = forms.CharField(
        required=False,
        label="Rejection reason",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Optional note stored on each rejected application."
    )

@admin.register(VendorApplication)
class VendorApplicationAdmin(admin.ModelAdmin):
    list_display  = ("id", "user", "company_name", "status", "created_at", "decided_by", "decided_at")
    list_filter   = ("status", "created_at")
    search_fields = ("user__username", "user__email", "company_name")
    autocomplete_fields = ("user",)
    date_hierarchy = "created_at"

    action_form = VendorApplicationActionForm
    actions = ("approve_selected", "reject_selected")

    @admin.action(description="Approve selected applications")
    def approve_selected(self, request, queryset):
        qs = queryset.filter(status=VendorApplication.Status.PENDING).select_related("user")
        approved = 0
        for app in qs:
            app.approve(request.user)
            approved += 1
        skipped = queryset.count() - approved
        if approved:
            self.message_user(request, f"Approved {approved} application(s).", level=messages.SUCCESS)
        if skipped:
            self.message_user(request, f"Skipped {skipped} non-pending application(s).", level=messages.WARNING)

    @admin.action(description="Reject selected applications")
    def reject_selected(self, request, queryset):
        reason = request.POST.get("rejection_reason") or "Rejected via admin."
        qs = queryset.filter(status=VendorApplication.Status.PENDING)
        rejected = 0
        for app in qs:
            app.reject(request.user, note=reason)
            rejected += 1
        skipped = queryset.count() - rejected
        if rejected:
            self.message_user(request, f"Rejected {rejected} application(s).", level=messages.WARNING)
        if skipped:
            self.message_user(request, f"Skipped {skipped} non-pending application(s).", level=messages.INFO)

@admin.register(VendorStaff)
class VendorStaffAdmin(admin.ModelAdmin):
    list_display  = ("id", "owner", "staff", "role", "is_active", "created_at")
    list_filter   = ("role", "is_active")
    search_fields = ("owner__username", "owner__email", "staff__username", "staff__email")
    autocomplete_fields = ("owner", "staff")
