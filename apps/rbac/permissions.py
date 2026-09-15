"""API 层权限装饰 — 菜单可见性与接口校验双重控制。"""
from functools import wraps

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from apps.core.exceptions import BusinessException
from apps.rbac.services import PermissionService


class IsSystemUser(BasePermission):
    """仅允许运营 SystemUser 访问管理端接口。"""

    message = "Access is restricted to operations principals"

    def has_permission(self, request, view):
        from apps.rbac.models import SystemUser

        user = getattr(request, "user", None)
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and isinstance(user, SystemUser)
        )


def require_permission(permission_code: str):
    """ViewSet action 装饰器：校验 JWT 用户是否具备指定权限码。"""

    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            user = getattr(request, "user", None)
            user_id = getattr(user, "id", None) or getattr(user, "pk", None)
            if not user_id:
                raise PermissionDenied("Authentication credentials were not provided")
            try:
                PermissionService().check_permission(str(user_id), permission_code)
            except BusinessException as exc:
                raise PermissionDenied(exc.message)
            return func(self, request, *args, **kwargs)

        return wrapper

    return decorator


class RequiresFeature:
    """Mixin: the authenticated SystemUser must hold feature_code (or Super Admin)."""

    feature_code = None
    ACTION_FEATURES = {}
    _READ_METHODS = {"GET", "HEAD", "OPTIONS"}

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.check_feature(request)

    def resolve_feature_code(self, request):
        action = getattr(self, "action", None) or (getattr(request, "method", "") or "").lower()
        return self.ACTION_FEATURES.get(action) or self.feature_code

    def check_feature(self, request):
        code = self.resolve_feature_code(request)
        if not code:
            return
        from apps.rbac.models import SystemUser

        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            raise PermissionDenied("Authentication credentials were not provided")
        if not isinstance(user, SystemUser):
            raise PermissionDenied("Access is restricted to operations principals")
        user_id = getattr(user, "id", None) or getattr(user, "pk", None)
        action = getattr(self, "action", None)
        mapped = action in getattr(self, "ACTION_FEATURES", {})
        service = PermissionService()
        try:
            if mapped:
                service.check_permission(str(user_id), code)
            elif (getattr(request, "method", "") or "").upper() in self._READ_METHODS:
                service.check_page_access(str(user_id), code)
            else:
                service.check_permission(str(user_id), code)
        except BusinessException as exc:
            raise PermissionDenied(exc.message)
