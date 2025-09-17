from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model

from .constants import VENDOR

from .constants import VENDOR, VENDOR_STAFF, DRIVER


User = settings.AUTH_USER_MODEL


# Create your models here.
class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        VENDOR = "vendor", "Vendor"
        VENDOR_STAFF = "vendor_staff", "Vendor Staff"
        DRIVER = "driver", "Driver"
        ADMIN = "admin", "Admin"

    email = models.EmailField(unique=True, max_length=191)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    is_member = models.BooleanField(default=True)
    # Explicit role for RBAC; default to customer for new users
    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.CUSTOMER,
        blank=True,
    )
    def __str__(self):
        return self.username


    @property
    def effective_role(self) -> str:
        """
        Resolve the user's effective role with the following priority:
        1) is_superuser or is_staff -> 'admin'
        2) if explicit `role` is set and valid -> that value
        3) infer from legacy relations/groups:
           - Group 'Vendor' -> 'vendor'
           - VendorStaff row where this user is staff (active) -> 'vendor_staff'
           - Group 'Driver' -> 'driver'
           - else -> 'customer'
        """
        try:
            if self.is_superuser or self.is_staff:
                return self.Role.ADMIN

            # Return explicit role if valid
            if self.role in {c for c, _ in self.Role.choices}:
                return self.role

            # Infer from groups/relations
            try:
                if self.groups.filter(name=VENDOR).exists():
                    return self.Role.VENDOR
            except Exception:
                pass

            try:
                if VendorStaff.objects.filter(staff_id=self.id, is_active=True).exists():
                    return self.Role.VENDOR_STAFF
            except Exception:
                pass

            try:
                if self.groups.filter(name=DRIVER).exists():
                    return self.Role.DRIVER
            except Exception:
                pass

            return self.Role.CUSTOMER
        except Exception:
            # Defensive default
            return self.Role.CUSTOMER

    @property
    def role_label(self) -> str:
        """Human-readable label corresponding to effective_role."""
        mapping = dict(self.Role.choices)
        code = self.effective_role
        return mapping.get(code, code)



class VendorApplication(models.Model):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    STATUS_CHOICES = [(PENDING, "Pending"), (APPROVED, "Approved"), (REJECTED, "Rejected")]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="vendor_applications")
    company_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=32, blank=True)
    note = models.TextField(blank=True)
    kra_pin = models.CharField(max_length=32, blank=True)
    national_id = models.CharField(max_length=32, blank=True)
    document = models.FileField(upload_to="kyc/", blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    decided_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


    def save(self, *args, **kwargs):
        # Track status change for downstream signals, in addition to existing pre_save hook
        try:
            if self.pk:
                prev = type(self).objects.only("status").get(pk=self.pk).status
                self._status_changed = (prev != self.status)
            else:
                self._status_changed = True
        except Exception:
            self._status_changed = True
        return super().save(*args, **kwargs)


    def approve(self, staff_user):
        from django.contrib.auth.models import Group
        self.status = self.APPROVED
        self.decided_by = staff_user
        self.decided_at = timezone.now()
        self.save(update_fields=["status", "decided_by", "decided_at"])
        Group.objects.get_or_create(name=VENDOR)[0].user_set.add(self.user)
        VendorStaff.objects.get_or_create(owner=self.user, staff=self.user, defaults={"role": VendorStaff.Role.OWNER})

    def reject(self, staff_user, note=""):
        self.status = self.REJECTED
        self.note = note or self.note
        self.decided_by = staff_user
        self.decided_at = timezone.now()
        self.save(update_fields=["status", "note", "decided_by", "decided_at"])


class VendorStaff(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        STAFF = "staff", "Staff"

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="vendor_staff_owned")
    staff = models.ForeignKey(User, on_delete=models.CASCADE, related_name="vendor_staff_memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STAFF)

    scopes = models.JSONField(default=list, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "staff"], name="uniq_vendorstaff_owner_staff"),
            models.CheckConstraint(check=~models.Q(owner=models.F("staff")), name="vendorstaff_owner_not_staff"),
        ]

    def clean(self):
        if self.owner_id == self.staff_id:
            # only valid when role is owner
            if self.role != self.Role.OWNER:

                raise ValidationError("Owner cannot be added as staff unless role='owner'.")

                raise ValidationError("Owner cannot be added as staff unless role='owner'.")

