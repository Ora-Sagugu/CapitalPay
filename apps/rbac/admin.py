"""Django Admin 注册 RBAC 模型。"""
from django.contrib import admin
from .models import SystemUser, Role, Permission, UserRole, RolePermission, OperationLog


@admin.register(SystemUser)
class SystemUserAdmin(admin.ModelAdmin):
    list_display = ["username", "real_name", "phone", "is_active", "is_locked", "last_login_at"]
    list_filter = ["is_active", "is_locked"]
    search_fields = ["username", "real_name", "phone"]


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_system", "description"]
    search_fields = ["name", "code"]


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "resource", "action"]
    list_filter = ["resource"]
    search_fields = ["code", "name"]


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "created_at"]


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ["role", "permission", "created_at"]


@admin.register(OperationLog)
class OperationLogAdmin(admin.ModelAdmin):
    list_display = ["username", "action", "resource", "status", "ip_address", "created_at"]
    list_filter = ["action", "status"]
    search_fields = ["username", "resource"]
    readonly_fields = list(admin.ModelAdmin.readonly_fields) + [f.name for f in OperationLog._meta.fields]
