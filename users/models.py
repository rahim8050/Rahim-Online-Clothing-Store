from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import F, Q



# Create your models here.
class CustomUser(AbstractUser):
    email = models.EmailField(unique=True, max_length=191)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    is_member = models.BooleanField(default=True)
    def __str__(self):
        return self.username


class VendorStaff(models.Model):
    owner = models.ForeignKey(
        CustomUser, related_name="owned_staff", on_delete=models.CASCADE
    )
    staff = models.ForeignKey(
        CustomUser, related_name="vendor_memberships", on_delete=models.CASCADE
    )
    status = models.CharField(
        max_length=8,
        choices=[("pending", "pending"), ("accepted", "accepted"), ("disabled", "disabled")],
        default="pending",
    )
    is_active = models.BooleanField(default=False)
    invited_at = models.DateTimeField(auto_now_add=True, null=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    last_emailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "staff"], name="uniq_owner_staff"
            ),
            models.CheckConstraint(
                check=~Q(owner=F("staff")), name="no_self_membership"
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "is_active"]),
            models.Index(fields=["staff", "is_active"]),
            models.Index(fields=["status"]),
        ]
