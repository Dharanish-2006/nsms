from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Only approved users whose role is "admin". Enforced here, not just in the UI."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role == "admin"
            and user.status == "active"
        )


class IsPlantOwner(BasePermission):
    """Approved plant owners (role "user"). Monitoring, reports, alerts and settings are theirs;
    admins run the system and have no access to machine data."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.role == "user" and user.status == "active"
        )
