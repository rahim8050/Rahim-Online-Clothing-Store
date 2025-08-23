from rest_framework.permissions import BasePermission
from users.constants import VENDOR, VENDOR_STAFF, DRIVER
from users.utils import in_groups


class InGroups(BasePermission):
    required_groups: tuple[str, ...] = ()

    def has_permission(self, request, view):
        return in_groups(request.user, *self.required_groups)


class IsDriver(InGroups):
    required_groups = (DRIVER,)


class IsVendorOrStaff(InGroups):
    required_groups = (VENDOR, VENDOR_STAFF)


