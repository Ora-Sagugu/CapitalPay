"""RBAC DRF 序列化器 — 账号、角色、权限的序列化。"""
from rest_framework import serializers
from .models import SystemUser, Role, Permission, UserRole, OperationLog, RolePermission


class LoginSerializer(serializers.Serializer):
    account = serializers.CharField(max_length=128)
    password = serializers.CharField(max_length=128)


class SystemUserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = SystemUser
        fields = [
            "id", "username", "real_name", "phone", "email",
            "is_active", "is_locked", "roles",
            "last_login_at", "last_login_ip",
            "created_at",
        ]
        read_only_fields = ["id", "last_login_at", "last_login_ip", "created_at"]

    def get_roles(self, obj):
        return list(UserRole.objects.filter(
            user=obj, is_deleted=False
        ).values_list("role__code", flat=True))


class SystemUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    role_codes = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)

    class Meta:
        model = SystemUser
        fields = [
            "username", "password", "real_name", "phone", "email", "role_codes",
        ]


class PasswordResetSerializer(serializers.Serializer):
    new_password = serializers.CharField(min_length=6)


class RoleSerializer(serializers.ModelSerializer):
    permission_count = serializers.SerializerMethodField()
    permission_codes = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False
    )
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = [
            "id", "name", "code", "description", "is_system",
            "permission_count", "permissions", "permission_codes",
            "created_at",
        ]
        read_only_fields = ["id", "is_system", "created_at"]

    def get_permission_count(self, obj):
        return RolePermission.objects.filter(role=obj, is_deleted=False).count()

    def get_permissions(self, obj):
        return list(RolePermission.objects.filter(
            role=obj, is_deleted=False
        ).values_list("permission__code", flat=True))


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = [
            "id", "code", "name", "resource", "action",
            "description", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class RolePermissionAssignSerializer(serializers.Serializer):
    permission_codes = serializers.ListField(child=serializers.CharField())


class UserRoleAssignSerializer(serializers.Serializer):
    role_codes = serializers.ListField(child=serializers.CharField())


class FunctionRoleAssignSerializer(serializers.Serializer):
    role_codes = serializers.ListField(child=serializers.CharField(), allow_empty=True)


class RoleCapabilityAssignSerializer(serializers.Serializer):
    capability_codes = serializers.ListField(child=serializers.CharField(), allow_empty=True)


class OperationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationLog
        fields = [
            "id", "username", "action", "resource", "resource_id",
            "detail", "status", "ip_address", "created_at",
        ]
