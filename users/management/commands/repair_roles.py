"""
Normalize and repair user.role across the database based on effective role.

This command computes each user's effective role (via the User.effective_role
property if present, falling back to inference rules) and updates the stored
`role` field to match.

Examples:
- python manage.py repair_roles
- python manage.py repair_roles --dry-run --only-missing --verbose
- python manage.py repair_roles --limit 5000 --batch-size 500

The command is designed for large tables and MySQL, supports batching and
skip-locked row selection when not in dry-run mode, and handles missing related
apps/models gracefully.
"""

from __future__ import annotations

from typing import Dict, Optional, Set

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import DatabaseError, transaction
from django.db.models import Q

try:
    # Django's NotSupportedError for select_for_update options
    from django.db.utils import NotSupportedError  # type: ignore
except Exception:  # pragma: no cover - very old Django
    NotSupportedError = Exception  # type: ignore


# Default set of valid roles if User.role choices are not discoverable.
DEFAULT_VALID_ROLES: Set[str] = {
    "customer",
    "vendor",
    "vendor_staff",
    "driver",
    "admin",
}


# Lazy caches for optional relations
_VENDOR_MODEL = None
_VENDOR_MODEL_TRIED = False

_VENDOR_STAFF_MODEL = None
_VENDOR_STAFF_MODEL_TRIED = False

# Prefer project group names if available
try:
    from users.constants import VENDOR as _VENDOR_GROUP_NAME, VENDOR_STAFF as _VENDOR_STAFF_GROUP_NAME, DRIVER as _DRIVER_GROUP_NAME  # type: ignore
except Exception:
    _VENDOR_GROUP_NAME = "Vendor"
    _VENDOR_STAFF_GROUP_NAME = "Vendor Staff"
    _DRIVER_GROUP_NAME = "Driver"


def _get_valid_roles(User) -> Set[str]:
    """Try to read valid choices from the User.role field; fall back to defaults."""
    try:
        field = User._meta.get_field("role")
        choices = getattr(field, "choices", None)
        if choices:
            return {c[0] for c in choices}
    except Exception:
        pass
    return set(DEFAULT_VALID_ROLES)


def _resolve_vendor_model():
    global _VENDOR_MODEL, _VENDOR_MODEL_TRIED
    if _VENDOR_MODEL_TRIED:
        return _VENDOR_MODEL
    _VENDOR_MODEL_TRIED = True
    try:
        from vendors.models import Vendor  # type: ignore

        _VENDOR_MODEL = Vendor
    except Exception:
        _VENDOR_MODEL = None
    return _VENDOR_MODEL


def _resolve_vendor_staff_model():
    global _VENDOR_STAFF_MODEL, _VENDOR_STAFF_MODEL_TRIED
    if _VENDOR_STAFF_MODEL_TRIED:
        return _VENDOR_STAFF_MODEL
    _VENDOR_STAFF_MODEL_TRIED = True
    try:
        # Assumption says possibly users.models.VendorStaff (or similar). We'll try this path.
        from users.models import VendorStaff  # type: ignore

        _VENDOR_STAFF_MODEL = VendorStaff
    except Exception:
        _VENDOR_STAFF_MODEL = None
    return _VENDOR_STAFF_MODEL


def compute_effective_role(u) -> str:
    """Compute effective role for a user.

    Priority:
    1) is_superuser or is_staff -> 'admin'
    2) if explicit `role` is a valid choice -> that value
    3) infer from relations/groups:
       - Vendor relation -> 'vendor'
       - VendorStaff relation -> 'vendor_staff'
       - Group 'Drivers' -> 'driver'
       - else -> 'customer'

    If the model exposes `effective_role`, prefer that value.
    """
    # First, if the User model provides a property `effective_role`, respect it.
    try:
        if hasattr(u, "effective_role"):
            val = u.effective_role  # property access
            if isinstance(val, str) and val:
                return val
    except Exception:
        # If the property computation itself raised, continue to fallback logic.
        pass

    # Fallback logic, resilient to missing relations/apps.
    # Admin privilege overrides any explicit or inferred role.
    if getattr(u, "is_superuser", False) or getattr(u, "is_staff", False):
        return "admin"

    # If the explicit role looks valid, return it.
    valid_roles = getattr(u, "_valid_roles_cache", None)
    if not valid_roles:
        # Last resort, use defaults (this function can be used without the cmd context).
        valid_roles = DEFAULT_VALID_ROLES
    explicit = getattr(u, "role", None)
    if isinstance(explicit, str) and explicit in valid_roles:
        return explicit

    # Try vendor relation
    try:
        Vendor = _resolve_vendor_model()
        if Vendor is not None and getattr(u, "id", None) is not None:
            # Use user_id lookup to avoid an unnecessary join.
            if Vendor.objects.filter(user_id=u.id).only("id").exists():
                return "vendor"
    except Exception:
        pass

    # Try group membership for 'Vendor'
    try:
        if getattr(u, "id", None) is not None and u.groups.filter(name=_VENDOR_GROUP_NAME).exists():
            return "vendor"
    except Exception:
        pass

    # Try vendor staff relation (users.VendorStaff where staff is the user)
    try:
        VendorStaff = _resolve_vendor_staff_model()
        if VendorStaff is not None and getattr(u, "id", None) is not None:
            if VendorStaff.objects.filter(staff_id=u.id, is_active=True).only("id").exists():
                return "vendor_staff"
    except Exception:
        pass

    # Try group membership for 'Vendor Staff'
    try:
        if getattr(u, "id", None) is not None and u.groups.filter(name=_VENDOR_STAFF_GROUP_NAME).exists():
            return "vendor_staff"
    except Exception:
        pass

    # Try group membership for 'Driver'
    try:
        if getattr(u, "id", None) is not None and u.groups.filter(name=_DRIVER_GROUP_NAME).exists():
            return "driver"
    except Exception:
        pass

    # Default: customer
    return "customer"


def log_change(u, old: Optional[str], new: Optional[str], verbose: bool) -> None:
    """Print a per-user decision line when verbose is requested."""
    if not verbose:
        return
    uid = getattr(u, "id", None)
    uname = getattr(u, "username", "")
    old_s = "" if old is None else str(old)
    new_s = "" if new is None else str(new)
    # Follow the requested output format
    if old_s != new_s:
        print(f"[CHANGE] user={uid} username={uname} role: '{old_s}' -> '{new_s}'")
    else:
        print(f"[OK]     user={uid} username={uname} role: '{old_s}'")


def _should_consider_user(u, valid_roles: Set[str]) -> bool:
    """Helper used only when --only-missing is applied at Python level (rare)."""
    r = getattr(u, "role", None)
    if r is None:
        return True
    if isinstance(r, str) and (r.strip() == "" or r not in valid_roles):
        return True
    return False


def process_batch(qs, opts: Dict) -> Dict[str, int]:
    """Process a queryset slice within a DB transaction.

    Returns counters: scanned, changed, unchanged, errors, skipped.
    """
    dry_run: bool = bool(opts.get("dry_run", False))
    verbose: bool = bool(opts.get("verbose", False))
    valid_roles: Set[str] = opts["valid_roles"]
    only_missing: bool = bool(opts.get("only_missing", False))

    stats = {"scanned": 0, "changed": 0, "unchanged": 0, "errors": 0, "skipped": 0}

    # Ensure we always run in a transaction; locking is only applied when not dry-run.
    with transaction.atomic():
        batch_qs = qs
        if not dry_run:
            # Try to avoid lock contention in production.
            try:
                batch_qs = batch_qs.select_for_update(skip_locked=True)
            except (NotSupportedError, DatabaseError):
                try:
                    batch_qs = batch_qs.select_for_update()
                except Exception:
                    # Fallback: no locking
                    pass

        processed_any = False
        # Use iterator to avoid large memory usage; chunk size can be generous here.
        for u in batch_qs.iterator(chunk_size=2000):
            processed_any = True
            try:
                # Attach valid roles cache for compute_effective_role fallback path.
                setattr(u, "_valid_roles_cache", valid_roles)

                if only_missing and not _should_consider_user(u, valid_roles):
                    stats["skipped"] += 1
                    continue

                stats["scanned"] += 1
                old = getattr(u, "role", None)
                new = compute_effective_role(u)

                if old != new:
                    log_change(u, old, new, verbose)
                    if not dry_run:
                        try:
                            u.role = new
                            u.save(update_fields=["role"])
                        except Exception as save_exc:  # capture and continue
                            stats["errors"] += 1
                            print(
                                f"[ERROR] user={getattr(u,'id',None)} save failed: {save_exc}"
                            )
                            continue
                    stats["changed"] += 1
                else:
                    log_change(u, old, new, verbose)
                    stats["unchanged"] += 1
            except Exception as exc:
                stats["errors"] += 1
                print(f"[ERROR] user={getattr(u,'id',None)} compute failed: {exc}")

        # If skip_locked was used, some rows might be skipped implicitly; we don't count those.
        # processed_any helps detect the final empty slice without an extra COUNT.
        if not processed_any:
            # No rows in this slice
            pass

    return stats


class Command(BaseCommand):
    help = (
        "Normalize user.role based on effective role. Safe, idempotent, and supports batching."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=False, help="Do not write changes; only report.")
        parser.add_argument("--limit", type=int, default=None, help="Process at most N users.")
        parser.add_argument("--offset", type=int, default=None, help="Skip first N users.")
        parser.add_argument(
            "--only-missing",
            action="store_true",
            default=False,
            help="Process only users whose role is NULL/empty/invalid.",
        )
        parser.add_argument("--verbose", action="store_true", default=False, help="Print per-user decisions.")
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Commit after each batch of N users (default 1000).",
        )

    def handle(self, *args, **options):
        dry_run: bool = bool(options.get("dry_run", False))
        limit: Optional[int] = options.get("limit")
        offset: Optional[int] = options.get("offset")
        only_missing: bool = bool(options.get("only_missing", False))
        verbose: bool = bool(options.get("verbose", False))
        batch_size: int = int(options.get("batch_size") or 1000)

        User = get_user_model()
        valid_roles = _get_valid_roles(User)

        # Build base queryset
        base_qs = (
            User.objects.all()
            .only("id", "role", "is_staff", "is_superuser")
            .order_by("id")
        )

        # Filter only missing/invalid roles if requested.
        if only_missing:
            base_qs = base_qs.filter(
                Q(role__isnull=True) | Q(role__exact="") | ~Q(role__in=list(valid_roles))
            )

        # Apply offset/limit slicing in SQL where possible.
        start = int(offset or 0)
        end = None
        if limit is not None:
            end = start + int(limit)
        if start or end is not None:
            base_qs = base_qs[start:end]

        # Iterate in batches, each in its own transaction. Avoid COUNT for performance.
        totals = {"scanned": 0, "changed": 0, "unchanged": 0, "errors": 0, "skipped": 0}
        pos = 0

        opts = {
            "dry_run": dry_run,
            "verbose": verbose,
            "only_missing": only_missing,
            "valid_roles": valid_roles,
        }

        while True:
            slice_qs = base_qs[pos : pos + batch_size]

            # Peek by trying to iterate; if empty, break. We rely on process_batch's transaction.
            # To detect emptiness without double-querying the entire slice, try a quick values_list.
            id_list = list(slice_qs.values_list("id", flat=True)[:1])
            if not id_list:
                break

            # Recreate slice_qs to ensure we still have the same only/order and constraints.
            slice_qs = base_qs[pos : pos + batch_size]

            stats = process_batch(slice_qs, opts)
            for k in totals:
                totals[k] += stats.get(k, 0)

            # Advance window
            pos += batch_size

        # Final summary
        summary = (
            f"Scanned: {totals['scanned']} | Changed: {totals['changed']} | "
            f"Unchanged: {totals['unchanged']} | Skipped: {totals['skipped']} | Errors: {totals['errors']}"
        )
        self.stdout.write(summary)


# ---
# Minimal pytest-style snippet (commented) for quick verification.
#
# def test_repair_roles_admin_and_vendor(django_db_blocker):
#     from django.core.management import call_command
#     from django.contrib.auth import get_user_model
#     with django_db_blocker.unblock():
#         User = get_user_model()
#         admin = User.objects.create(username="admin1", is_staff=True, role="customer")
#         vendor_user = User.objects.create(username="vendor1", role="")
#         # If vendors.models.Vendor exists with FK user -> create it; else skip.
#         try:
#             from vendors.models import Vendor
#             Vendor.objects.create(user=vendor_user)
#         except Exception:
#             pass
#
#         call_command("repair_roles")
#         admin.refresh_from_db()
#         vendor_user.refresh_from_db()
#
#         assert admin.role == "admin"
#         # If Vendor model exists, vendor_user becomes vendor; otherwise falls back to customer.
#         try:
#             from vendors.models import Vendor
#             assert vendor_user.role == "vendor"
#         except Exception:
#             assert vendor_user.role in {"customer", "vendor"}
