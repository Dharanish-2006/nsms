from django.contrib import admin, messages

from .models import Gateway, GatewayAssignment, Machine, Plant


class AssignmentInline(admin.TabularInline):
    """History only. Assigning and connecting go through the Admin Portal, which enforces the
    rules and writes the audit log."""

    model = GatewayAssignment
    extra = 0
    can_delete = False
    fields = ["user", "status", "assigned_at", "connected_at", "disconnected_at"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class MachineInline(admin.TabularInline):
    model = Machine
    extra = 0
    fields = ["id", "name", "type", "meter_id", "rated_kw", "on_threshold_kw", "position"]


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Gateway)
class GatewayAdmin(admin.ModelAdmin):
    list_display = ["name", "serial_number", "plant", "verified", "enabled", "api_key_prefix", "last_seen_at"]
    list_filter = ["plant", "verified", "enabled"]
    readonly_fields = ["api_key_prefix", "last_seen_at", "last_ip", "created_at"]
    exclude = ["api_key_hash"]
    inlines = [MachineInline, AssignmentInline]
    actions = ["rotate_keys"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        key = getattr(obj, "_first_key", None)
        if key:
            messages.warning(request, f"API key for {obj.name} (shown once, copy it now): {key}")

    @admin.action(description="Issue a new API key (the old one stops working)")
    def rotate_keys(self, request, queryset):
        for gateway in queryset:
            key = gateway.rotate_key()
            gateway.save(update_fields=["api_key_prefix", "api_key_hash"])
            messages.warning(request, f"New API key for {gateway.name} (shown once): {key}")


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "type", "gateway", "meter_id", "rated_kw"]
    list_filter = ["type", "gateway"]
    search_fields = ["id", "name"]
