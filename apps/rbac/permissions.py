"""API 层权限装饰 — 菜单可见性与接口校验双重控制。"""
from functools import wraps

from rest_framework.exceptions import PermissionDenied

from apps.core.exceptions import BusinessException
from apps.rbac.services import PermissionService


def require_permission(permission_code: str):
    """ViewSet action 装饰器：校验 JWT 用户是否具备指定权限码。"""

    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            user = getattr(request, "user", None)
            user_id = getattr(user, "id", None) or getattr(user, "pk", None)
            if not user_id:
                raise PermissionDenied("未登录")
            try:
                PermissionService().check_permission(str(user_id), permission_code)
            except BusinessException as exc:
                raise PermissionDenied(exc.message)
            return func(self, request, *args, **kwargs)

        return wrapper

    return decorator
