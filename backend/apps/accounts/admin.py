from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


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
