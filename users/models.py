from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from .constants import VENDOR

User = settings.AUTH_USER_MODEL


# Create your models here.
class CustomUser(AbstractUser):
    email = models.EmailField(unique=True, max_length=191)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    is_member = models.BooleanField(default=True)
    def __str__(self):
        return self.username


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