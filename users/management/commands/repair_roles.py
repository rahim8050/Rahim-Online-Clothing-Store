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

import sys
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import DatabaseError, transaction
from django.db.models import Q, QuerySet

# ---------------------------------------------------------------------
# Safe import for NotSupportedError (some DBs may not define it)
# ---------------------------------------------------------------------
try:
    from django.db.utils import NotSupportedError
except ImportError:  # pragma: no cover

    class NotSupportedError(Exception):  # type: ignore[misc]
        """Fallback when Django doesn't define NotSupportedError."""

        pass


# ---------------------------------------------------------------------
# Constants & caches
# ---------------------------------------------------------------------
DEFAULT_VALID_ROLES: set[str] = {
    "customer",
    "vendor",
    "vendor_staff",
    "driver",
    "admin",
}

_VENDOR_MODEL: Any | None = None
_VENDOR_MODEL_TRIED: bool = False

_VENDOR_STAFF_MODEL: Any | None = None
_VENDOR_STAFF_MODEL_TRIED: bool = False

try:
    from users.constants import DRIVER as _DRIVER_GROUP_NAME
    from users.constants import VENDOR as _VENDOR_GROUP_NAME
    from users.constants import VENDOR_STAFF as _VENDOR_STAFF_GROUP_NAME
except Exception:
    _VENDOR_GROUP_NAME = "Vendor"
    _VENDOR_STAFF_GROUP_NAME = "Vendor Staff"
    _DRIVER_GROUP_NAME = "Driver"


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------
def _get_valid_roles(User: Any) -> set[str]:
    """Try to read valid choices from the User.role field; fall back to defaults."""
    try:
        field = User._meta.get_field("role")
        choices = getattr(field, "choices", None)
        if choices:
            return {c[0] for c in choices}
    except Exception:
        pass
    return set(DEFAULT_VALID_ROLES)


def _resolve_vendor_model() -> Any | None:
    """Return the Vendor model if importable."""
    global _VENDOR_MODEL, _VENDOR_MODEL_TRIED
    if _VENDOR_MODEL_TRIED:
        return _VENDOR_MODEL
    _VENDOR_MODEL_TRIED = True
    try:
        from vendor_app.models import Vendor  # ✅ fixed import path

        _VENDOR_MODEL = Vendor
    except Exception:
        _VENDOR_MODEL = None
    return _VENDOR_MODEL


def _resolve_vendor_staff_model() -> Any | None:
    """Return the VendorStaff model if importable."""
    global _VENDOR_STAFF_MODEL, _VENDOR_STAFF_MODEL_TRIED
    if _VENDOR_STAFF_MODEL_TRIED:
        return _VENDOR_STAFF_MODEL
    _VENDOR_STAFF_MODEL_TRIED = True
    try:
        from users.models import VendorStaff

        _VENDOR_STAFF_MODEL = VendorStaff
    except Exception:
        _VENDOR_STAFF_MODEL = None
    return _VENDOR_STAFF_MODEL


# ---------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------
def compute_effective_role(u: Any) -> str:
    """Compute effective role for a user based on multiple inference rules."""
    try:
        if hasattr(u, "effective_role"):
            val = u.effective_role
            if isinstance(val, str) and val:
                return val
    except Exception:
        pass

    if getattr(u, "is_superuser", False) or getattr(u, "is_staff", False):
        return "admin"

    valid_roles = getattr(u, "_valid_roles_cache", DEFAULT_VALID_ROLES)
    explicit = getattr(u, "role", None)
    if isinstance(explicit, str) and explicit in valid_roles:
        return explicit

    try:
        Vendor = _resolve_vendor_model()
        if Vendor is not None and getattr(u, "id", None) is not None:
            if Vendor.objects.filter(user_id=u.id).only("id").exists():
                return "vendor"
    except Exception:
        pass

    try:
        if u.groups.filter(name=_VENDOR_GROUP_NAME).exists():
            return "vendor"
    except Exception:
        pass

    try:
        VendorStaff = _resolve_vendor_staff_model()
        if VendorStaff is not None and getattr(u, "id", None) is not None:
            if (
                VendorStaff.objects.filter(staff_id=u.id, is_active=True)
                .only("id")
                .exists()
            ):
                return "vendor_staff"
    except Exception:
        pass

    try:
        if u.groups.filter(name=_VENDOR_STAFF_GROUP_NAME).exists():
            return "vendor_staff"
    except Exception:
        pass

    try:
        if u.groups.filter(name=_DRIVER_GROUP_NAME).exists():
            return "driver"
    except Exception:
        pass

    return "customer"


def log_change(u: Any, old: str | None, new: str | None, verbose: bool) -> None:
    """Print a per-user decision line when verbose is requested."""
    if not verbose:
        return
    uid = getattr(u, "id", None)
    uname = getattr(u, "username", "")
    old_s = "" if old is None else str(old)
    new_s = "" if new is None else str(new)
    if old_s != new_s:
        print(f"[CHANGE] user={uid} username={uname} role: '{old_s}' -> '{new_s}'")
    else:
        print(f"[OK]     user={uid} username={uname} role: '{old_s}'")


def _should_consider_user(u: Any, valid_roles: set[str]) -> bool:
    """Helper used when --only-missing is applied at Python level."""
    r = getattr(u, "role", None)
    if r is None:
        return True
    if isinstance(r, str) and (r.strip() == "" or r not in valid_roles):
        return True
    return False


def process_batch(qs: QuerySet, opts: dict[str, Any]) -> dict[str, int]:
    """Process a queryset slice within a DB transaction."""
    dry_run = bool(opts.get("dry_run", False))
    verbose = bool(opts.get("verbose", False))
    valid_roles = opts["valid_roles"]
    only_missing = bool(opts.get("only_missing", False))

    stats: dict[str, int] = {
        "scanned": 0,
        "changed": 0,
        "unchanged": 0,
        "errors": 0,
        "skipped": 0,
    }

    with transaction.atomic():
        batch_qs = qs
        if not dry_run:
            try:
                batch_qs = batch_qs.select_for_update(skip_locked=True)
            except (NotSupportedError, DatabaseError):
                try:
                    batch_qs = batch_qs.select_for_update()
                except Exception:
                    pass

        for u in batch_qs.iterator(chunk_size=2000):
            try:
                u._valid_roles_cache = valid_roles
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
                        except Exception as save_exc:
                            stats["errors"] += 1
                            print(
                                f"[ERROR] user={getattr(u, 'id', None)} save failed: {save_exc}",
                                file=sys.stderr,
                            )
                            continue
                    stats["changed"] += 1
                else:
                    log_change(u, old, new, verbose)
                    stats["unchanged"] += 1
            except Exception as exc:
                stats["errors"] += 1
                print(
                    f"[ERROR] user={getattr(u, 'id', None)} compute failed: {exc}",
                    file=sys.stderr,
                )

    return stats


# ---------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------
class Command(BaseCommand):
    help = "Normalize user.role based on effective role. Safe, idempotent, and supports batching."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--dry-run", action="store_true", default=False)
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--offset", type=int, default=None)
        parser.add_argument("--only-missing", action="store_true", default=False)
        parser.add_argument("--verbose", action="store_true", default=False)
        parser.add_argument("--batch-size", type=int, default=1000)

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run = bool(options.get("dry_run", False))
        limit = options.get("limit")
        offset = options.get("offset")
        only_missing = bool(options.get("only_missing", False))
        verbose = bool(options.get("verbose", False))
        batch_size = int(options.get("batch_size") or 1000)

        User = get_user_model()
        valid_roles = _get_valid_roles(User)

        base_qs = (
            User.objects.all()
            .only("id", "role", "is_staff", "is_superuser")
            .order_by("id")
        )

        if only_missing:
            base_qs = base_qs.filter(
                Q(role__isnull=True)
                | Q(role__exact="")
                | ~Q(role__in=list(valid_roles))
            )

        start = int(offset or 0)
        end = None
        if limit is not None:
            end = start + int(limit)
        if start or end is not None:
            base_qs = base_qs[start:end]

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
            if not slice_qs.exists():
                break

            stats = process_batch(slice_qs, opts)
            for k in totals:
                totals[k] += stats.get(k, 0)
            pos += batch_size

        summary = (
            f"Scanned: {totals['scanned']} | Changed: {totals['changed']} | "
            f"Unchanged: {totals['unchanged']} | Skipped: {totals['skipped']} | Errors: {totals['errors']}"
        )
        self.stdout.write(summary)
