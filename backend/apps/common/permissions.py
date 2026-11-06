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


class AdminWritesMixin:
    """Reads are open to any signed-in user (scoped to what they may see);
    every write needs the admin role."""

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return super().get_permissions()
        return [IsAdminRole()]
