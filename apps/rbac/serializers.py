"""RBAC DRF 序列化器 — 账号、角色、权限的序列化。"""
import re

from rest_framework import serializers

from .functions import RETIRED_ROLE_CODES, SYSTEM_ROLE_CODES
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

    def validate_code(self, value):
        code = (value or "").strip()
        if not code:
            raise serializers.ValidationError("Role code is required.")
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", code):
            raise serializers.ValidationError(
                "Use lowercase letters, digits and underscores, starting with a letter."
            )
        if self.instance is None and (
            code in SYSTEM_ROLE_CODES or code in RETIRED_ROLE_CODES
        ):
            raise serializers.ValidationError("This role code is reserved by the system.")
        return code

    def validate_name(self, value):
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("Role name is required.")
        return name

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
