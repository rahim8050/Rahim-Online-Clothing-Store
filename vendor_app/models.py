"""
Enterprise vendor multi-tenant foundations.

Overview
--------
This module introduces organization-scoped vendor entities while preserving
legacy compatibility where a "vendor" maps to a single `users.CustomUser`.

Key concepts:
- VendorOrg: A vendor organization (tenant). Has an owner (User) and can
  contain many members with roles.
- VendorMember: A user's membership within an organization, including org-
  scoped RBAC via role choices (OWNER | MANAGER | STAFF) and activation flag.
- VendorProfile: Optional compatibility bridge for legacy vendor flows where
  a single user represents a vendor. It links a primary org to a user without
  changing existing endpoints. This field is nullable and can be backfilled
  later.

Notes
-----
- This code is additive and does not alter existing endpoints. It is safe to
  migrate first, backfill later, and then introduce /apis/v1/vendor/* routes
  that use these models.
- All datetimes are timezone-aware (Django USE_TZ). Project TZ: Africa/Nairobi
  at the application level; stored in UTC.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.text import slugify

UserRef = settings.AUTH_USER_MODEL


class VendorOrg(models.Model):
    """A vendor organization (tenant) with org-scoped RBAC.

    - `owner` is the primary account holder for the org.
    - `slug` is unique and stable for future org-scoped URLs.
    - `is_active` soft-switch to disable the org without deleting.

    Helper methods provide RBAC checks and member management while keeping
    legacy routes intact.
    """

    name: str = models.CharField(max_length=120)
    slug: str = models.SlugField(max_length=140, unique=True, db_index=True)
    owner = models.ForeignKey(
        UserRef,
        on_delete=models.PROTECT,
        related_name="owned_vendor_orgs",
        db_index=True,
    )
    is_active: bool = models.BooleanField(default=True)
    # Org-level commission (e.g., 0.02 for 2%) and payout channel for KE
    org_commission_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    org_payout_channel = models.CharField(
        max_length=16,
        choices=[("mpesa", "M-PESA"), ("bank", "Bank")],
        default="mpesa",
    )

    # Kenya tax details
    class TaxStatus(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        VERIFIED = "verified", "Verified"
        BLOCKED = "blocked", "Blocked"

    kra_pin = models.CharField(max_length=12, blank=True, default="")
    tax_status = models.CharField(
        max_length=16, choices=TaxStatus.choices, default=TaxStatus.UNKNOWN
    )
    tax_registered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["owner"], name="vendororg_owner_idx"),
        ]
        constraints = [
            # human-readable safety: slug normalized to lower-case characters
            models.CheckConstraint(
                check=~Q(slug=""),
                name="vendororg_slug_not_empty",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - representation only
        return f"{self.name} ({self.slug})"

    # --------------------- helpers / RBAC ---------------------
    def add_member(self, user, role: str) -> VendorMember:
        """Add or update a member with a role in this org.

        - Ensures only one OWNER per org (via partial unique constraint).
        - Reactivates soft-deactivated memberships.
        """
        role = (role or "").upper()
        if role not in VendorMember.Role.values:
            raise ValueError(f"Invalid role: {role}")

        member, created = VendorMember.objects.get_or_create(
            org=self, user=user, defaults={"role": role, "is_active": True}
        )
        if not created:
            # Update role and ensure active
            if member.role != role or not member.is_active:
                member.role = role
                member.is_active = True
                member.save(update_fields=["role", "is_active", "updated_at"])
        return member

    def is_member(self, user) -> bool:
        return VendorMember.objects.filter(org=self, user=user, is_active=True).exists()

    def has_role(self, user, role: str) -> bool:
        role = (role or "").upper()
        if role not in VendorMember.Role.values:
            return False
        return VendorMember.objects.filter(
            org=self, user=user, role=role, is_active=True
        ).exists()

    def save(self, *args, **kwargs):
        # keep slug normalized and unique
        if self.slug:
            self.slug = slugify(self.slug)
        elif self.name:
            self.slug = slugify(self.name)
        if getattr(self, "kra_pin", ""):
            self.kra_pin = (self.kra_pin or "").strip().upper()
        return super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()
        if getattr(self, "kra_pin", ""):
            import re

            pin = (self.kra_pin or "").strip().upper()
            if not re.match(r"^[A-Z]{1}[0-9]{9}[A-Z]{1}$", pin):
                raise ValidationError(
                    {"kra_pin": "KRA PIN must look like A123456789B."}
                )


class VendorMember(models.Model):
    """Membership of a `user` in a `VendorOrg` with role-based access.

    Constraints:
    - unique (org, user)
    - a single OWNER per org via a partial unique constraint
    - index on role for fast lookups
    """

    class Role(models.TextChoices):
        OWNER = "OWNER", "Owner"
        MANAGER = "MANAGER", "Manager"
        STAFF = "STAFF", "Staff"

        @property
        def values(self):  # type: ignore[override]
            return [c for c, _ in self.choices]

    org = models.ForeignKey(
        VendorOrg, related_name="members", on_delete=models.CASCADE, db_index=True
    )
    user = models.ForeignKey(
        UserRef,
        related_name="vendor_memberships",
        on_delete=models.CASCADE,
        db_index=True,
    )
    role = models.CharField(max_length=16, choices=Role.choices, db_index=True)
    is_active: bool = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["org", "user"], name="uniq_vendormember_org_user"
            ),
            # Enforce only one OWNER per org
            models.UniqueConstraint(
                fields=["org"],
                condition=Q(role="OWNER"),
                name="uniq_owner_per_org",
            ),
            models.CheckConstraint(
                check=~Q(role=""), name="vendormember_role_not_empty"
            ),
        ]
        indexes = [
            models.Index(fields=["role"], name="vendormember_role_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - representation only
        return f"{self.user_id}@{self.org_id}:{self.role}"

    def save(self, *args, **kwargs):
        # Cross-db safety: enforce single OWNER per org at application level
        # to cover backends without partial unique constraints (e.g. MySQL).
        if self.role == self.Role.OWNER:
            from django.db import transaction
            from django.db.utils import IntegrityError as DBIntegrityError

            with transaction.atomic():
                exists_qs = VendorMember.objects.select_for_update().filter(
                    org=self.org, role=self.Role.OWNER
                )
                if self.pk:
                    exists_qs = exists_qs.exclude(pk=self.pk)
                if exists_qs.exists():
                    # Align with DB error type used in tests for consistency
                    raise DBIntegrityError("Only one OWNER is allowed per org")
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)


class VendorProfile(models.Model):
    """Compatibility bridge mapping a legacy vendor user to a primary org.

    - Keeps existing flows intact by not changing any current models/routes.
    - `org` is nullable to allow a reversible, backfillable migration.
    - Use this only for mapping the primary/legacy vendor owner to an org.
      Do not use it for staff membership queries; use `VendorMember` instead.
    """

    user = models.OneToOneField(
        UserRef, on_delete=models.CASCADE, related_name="vendor_profile"
    )
    org = models.ForeignKey(
        VendorOrg,
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        related_name="profiles",
    )
    is_active: bool = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user"], name="vendorprofile_user_idx"),
            models.Index(fields=["org"], name="vendorprofile_org_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - representation only
        return f"VendorProfile(user={self.user_id}, org={self.org_id})"


class VendorOrgAuditLog(models.Model):
    actor = models.ForeignKey(
        UserRef,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_org_audit_entries",
    )
    org = models.ForeignKey(
        VendorOrg, on_delete=models.CASCADE, related_name="audit_entries"
    )
    field = models.CharField(max_length=64)
    old_value = models.TextField(blank=True, default="")
    new_value = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["org", "created_at"], name="vendororg_audit_idx"),
        ]
        verbose_name = "Vendor Org Audit Entry"
        verbose_name_plural = "Vendor Org Audit Entries"


class VendorKPI(models.Model):
    class Window(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    org = models.ForeignKey(VendorOrg, on_delete=models.CASCADE, related_name="kpis")
    window = models.CharField(max_length=16, choices=Window.choices, db_index=True)
    period_start = models.DateField()
    period_end = models.DateField()

    gross_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    orders = models.PositiveIntegerField(default=0)
    refunds = models.PositiveIntegerField(default=0)
    success_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )  # percent 0-100
    fulfillment_avg_mins = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["org", "window", "period_start"],
                name="uniq_vendor_kpi_window_start",
            ),
        ]
        indexes = [
            models.Index(
                fields=["org", "period_start", "window"], name="vendorkpi_org_date_idx"
            ),
        ]
