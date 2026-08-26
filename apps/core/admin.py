"""Admin configuration for core app."""
from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["operator", "action", "resource_type", "resource_id", "created_at"]
    list_filter = ["action", "resource_type", "created_at"]
    search_fields = ["operator", "resource_id"]
    readonly_fields = ["operator", "action", "resource_type", "resource_id",
                       "before_snapshot", "after_snapshot", "ip_address", "created_at"]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
