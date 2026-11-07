from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import AdminAuditLog, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "full_name", "email", "role", "status", "is_staff")
    list_filter = ("status", "role", "is_staff", "is_superuser")
    search_fields = ("username", "full_name", "email", "mobile")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Mill Monitor", {"fields": ("full_name", "mobile", "role", "requested_role", "status")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        (None, {"fields": ("email", "full_name", "mobile", "role", "status")}),
    )


@admin.register(AdminAuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only: the audit trail is append-only."""

    list_display = ("timestamp", "admin_username", "action", "target_type", "target_id", "remarks")
    list_filter = ("action",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
