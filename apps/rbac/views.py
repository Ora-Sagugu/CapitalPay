"""RBAC API 视图 — 登录、用户管理、角色管理、权限管理。"""
from django.db import models
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import BusinessException
from .authentication import JWTAuthentication
from .models import SystemUser, Role, Permission, RolePermission, OperationLog
from .permissions import RequiresFeature
from .serializers import (
    LoginSerializer, SystemUserSerializer, SystemUserCreateSerializer,
    PasswordResetSerializer, RoleSerializer, PermissionSerializer,
    RolePermissionAssignSerializer, UserRoleAssignSerializer, OperationLogSerializer,
    FunctionRoleAssignSerializer, RoleCapabilityAssignSerializer,
)
from .services import AuthService


class AuthViewSet(viewsets.ViewSet):
    """认证接口 — 登录、登出、刷新 Token。"""
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    auth_service = AuthService()

    @action(methods=["post"], detail=False, url_path="login")
    def login(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ip = request.META.get("REMOTE_ADDR", "")
        result = self.auth_service.admin_login(
            account=serializer.validated_data["account"],
            password=serializer.validated_data["password"],
            ip=ip,
        )
        return Response(result)

    @action(methods=["post"], detail=False, url_path="logout")
    def logout(self, request):
        """登出 — Token 校验由全局认证中间件完成。"""
        return Response({"message": "The session has been terminated"})

    @action(methods=["get"], detail=False, url_path="me")
    def me(self, request):
        self.auth_service.ensure_ops_rbac_if_needed()
        auth = JWTAuthentication()
        result = auth.authenticate(request)
        if result is None:
            raise BusinessException("UNAUTHORIZED", "Authentication is required", 401)
        user, _ = result
        serializer = SystemUserSerializer(user)
        data = serializer.data
        data["permissions"] = self.auth_service.get_user_permissions(str(user.id))
        data["license_warnings"] = self.auth_service._get_license_warnings()
        return Response(data)


class SystemUserViewSet(RequiresFeature, viewsets.ModelViewSet):
    """运营后台用户管理 — 创建、查询、锁定、重置密码。"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    feature_code = "feature:users"
    queryset = SystemUser.objects.filter(is_deleted=False)
    serializer_class = SystemUserSerializer
    lookup_field = "id"
    auth_service = AuthService()

    def get_serializer_class(self):
        if self.action == "create":
            return SystemUserCreateSerializer
        return SystemUserSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                models.Q(username__icontains=search)
                | models.Q(real_name__icontains=search)
                | models.Q(email__icontains=search)
                | models.Q(phone__icontains=search)
            )
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() in ("true", "1"))
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self.auth_service.create_user(**serializer.validated_data)
        return Response(SystemUserSerializer(user).data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        self.auth_service.create_user(**serializer.validated_data)

    def perform_update(self, serializer):
        user = serializer.save()
        return user

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @action(methods=["post"], detail=True, url_path="reset-password")
    def reset_password(self, request, id=None):
        user = self.get_object()
        s = PasswordResetSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        self.auth_service.reset_password(user, s.validated_data["new_password"])
        return Response({"message": "The password has been reset"})

    @action(methods=["post"], detail=True, url_path="lock")
    def lock(self, request, id=None):
        user = self.get_object()
        if self.auth_service.is_builtin_ops_user(user):
            raise BusinessException(
                "OPS_ACCOUNT_PROTECTED",
                "The built-in operations account cannot be locked",
                400,
            )
        self.auth_service.lock_user(user)
        return Response({"message": "The account has been locked"})

    @action(methods=["post"], detail=True, url_path="unlock")
    def unlock(self, request, id=None):
        user = self.get_object()
        self.auth_service.unlock_user(user)
        return Response({"message": "The account has been unlocked"})

    @action(methods=["post"], detail=True, url_path="toggle-status")
    def toggle_status(self, request, id=None):
        """启用/停用账号。"""
        user = self.get_object()
        if self.auth_service.is_builtin_ops_user(user) and user.is_active:
            raise BusinessException(
                "OPS_ACCOUNT_PROTECTED",
                "The built-in operations account cannot be disabled",
                400,
            )
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        return Response({
            "message": "The account has been enabled" if user.is_active else "The account has been disabled",
            "is_active": user.is_active,
        })

    @action(methods=["post"], detail=True, url_path="assign-roles")
    def assign_roles(self, request, id=None):
        user = self.get_object()
        s = UserRoleAssignSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        self.auth_service.assign_roles(user, s.validated_data["role_codes"])
        return Response({"message": "The roles have been assigned"})

    def perform_destroy(self, instance):
        """软删除 — 标记 is_deleted=True，停用账号。"""
        if self.auth_service.is_builtin_ops_user(instance):
            raise BusinessException(
                "OPS_ACCOUNT_PROTECTED",
                "The built-in operations account cannot be deleted",
                400,
            )
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active"])


class RoleViewSet(RequiresFeature, viewsets.ModelViewSet):
    """角色管理 — 创建、查询、授权。"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    feature_code = "feature:roles"
    queryset = Role.objects.filter(is_deleted=False)
    serializer_class = RoleSerializer
    auth_service = AuthService()

    def resolve_feature_code(self, request):
        if getattr(self, "action", None) in ("list", "retrieve"):
            user = getattr(request, "user", None)
            user_id = getattr(user, "id", None) or getattr(user, "pk", None)
            if user_id and self.auth_service.has_permission(str(user_id), "feature:users"):
                return "feature:users"
        return super().resolve_feature_code(request)

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) | models.Q(code__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        permission_codes = serializer.validated_data.pop("permission_codes", [])
        role = serializer.save()
        if permission_codes:
            self.auth_service.grant_permission(role, permission_codes)

    def perform_update(self, serializer):
        permission_codes = serializer.validated_data.pop("permission_codes", None)
        role = serializer.save()
        if permission_codes is not None:
            # 替换权限：硬删除旧记录，再创建新的（避免 unique_together 冲突）
            RolePermission.objects.filter(role=role).delete()
            self.auth_service.grant_permission(role, permission_codes)

    def perform_destroy(self, instance):
        if instance.is_system:
            raise BusinessException("SYSTEM_ROLE_PROTECTED", "A system-defined role cannot be deleted", 400)
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted"])

    @action(methods=["get"], detail=True, url_path="permissions")
    def list_role_permissions(self, request, pk=None):
        role = self.get_object()
        perms = RolePermission.objects.filter(
            role=role, is_deleted=False
        ).select_related("permission")
        perm_codes = [rp.permission.code for rp in perms]
        return Response({"role_code": role.code, "permissions": perm_codes})

    @action(methods=["post"], detail=True, url_path="grant")
    def grant_permissions(self, request, pk=None):
        role = self.get_object()
        s = RolePermissionAssignSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        self.auth_service.grant_permission(role, s.validated_data["permission_codes"])
        return Response({"message": "The entitlements have been granted"})

    @action(methods=["put"], detail=True, url_path="capabilities")
    def set_capabilities(self, request, pk=None):
        role = self.get_object()
        serializer = RoleCapabilityAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        codes = self.auth_service.set_role_capabilities(
            role, serializer.validated_data["capability_codes"]
        )
        return Response({"role_code": role.code, "capability_codes": codes})


class PermissionViewSet(RequiresFeature, viewsets.ReadOnlyModelViewSet):
    """权限查询 — 只读，权限由系统预定义。"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    feature_code = "feature:roles"
    queryset = Permission.objects.filter(is_deleted=False)
    serializer_class = PermissionSerializer


class FunctionViewSet(RequiresFeature, viewsets.ViewSet):
    """运营后台功能清单与角色挂载。"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    feature_code = "feature:roles"
    lookup_value_regex = r"[^/]+"
    auth_service = AuthService()

    def list(self, request):
        self.auth_service.ensure_ops_rbac_if_needed()
        return Response(self.auth_service.list_role_matrix())

    @action(methods=["put"], detail=True, url_path="roles")
    def set_roles(self, request, pk=None):
        serializer = FunctionRoleAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role_codes = self.auth_service.set_function_roles(pk, serializer.validated_data["role_codes"])
        return Response({"code": pk, "role_codes": role_codes})


class OperationLogViewSet(RequiresFeature, viewsets.ReadOnlyModelViewSet):
    """操作日志查询 — 只读。"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    feature_code = "feature:users"
    queryset = OperationLog.objects.all().select_related("user")
    serializer_class = OperationLogSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        action = self.request.query_params.get("action")
        if action:
            qs = qs.filter(action=action)
        username = self.request.query_params.get("username")
        if username:
            qs = qs.filter(username__icontains=username)
        return qs
