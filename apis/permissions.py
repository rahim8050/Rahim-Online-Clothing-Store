from rest_framework.permissions import BasePermission

class InGroups(BasePermission):
    """Allow access only to users in specific Django groups."""
    def has_permission(self, request, view):
        required = getattr(view, "required_groups", [])
        return (
            request.user
            and request.user.is_authenticated
            and request.user.groups.filter(name__in=required).exists()
        )
