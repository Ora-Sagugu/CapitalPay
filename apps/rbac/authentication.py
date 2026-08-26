"""JWT 认证类 — 运营后台和用户端通用。

Headers:
    Authorization: Bearer <token>
"""
from rest_framework import authentication, exceptions
from .services import AuthService


class JWTAuthentication(authentication.BaseAuthentication):
    """JWT Token 认证 — 用于运营后台和用户端的身份验证。"""

    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != self.keyword.lower():
            raise exceptions.AuthenticationFailed("Authorization 头格式错误，应为 Bearer <token>")

        token = parts[1]
        auth_service = AuthService()
        payload = auth_service._decode_token(token)

        user_id = payload.get("user_id")
        user_type = payload.get("user_type", "admin")

        if not user_id:
            raise exceptions.AuthenticationFailed("Token 中缺少 user_id")

        if user_type == "admin":
            from .models import SystemUser
            try:
                user = SystemUser.objects.get(id=user_id, is_active=True, is_deleted=False)
            except SystemUser.DoesNotExist:
                raise exceptions.AuthenticationFailed("用户不存在或已停用")
        elif user_type == "user":
            from apps.user_portal.models import EndUser
            try:
                user = EndUser.objects.get(id=user_id, is_active=True, is_deleted=False)
            except EndUser.DoesNotExist:
                raise exceptions.AuthenticationFailed("用户不存在或已停用")
        else:
            raise exceptions.AuthenticationFailed("无效的用户类型")

        return (user, payload)


class AllowAnyOrJWTAuthentication(JWTAuthentication):
    """可选的 JWT 认证 — 认证失败不报错，由权限类决定。"""

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except exceptions.AuthenticationFailed:
            return None
