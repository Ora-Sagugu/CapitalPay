"""RBAC 业务服务层 — 认证、授权、账号管理。"""
from __future__ import annotations
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

import jwt
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from datetime import date

from apps.core.exceptions import BusinessException, ErrorCode
from apps.merchant.models import Merchant
from .models import SystemUser, Role, Permission, UserRole, RolePermission, OperationLog


MAX_LOGIN_ATTEMPTS = 5
LOCK_DURATION_MINUTES = 30
TOKEN_EXPIRE_HOURS = 8


class AuthService:
    """认证与授权服务 — 登录、Token、权限校验。"""

    @staticmethod
    def _hash_password(password: str, salt: str = "") -> str:
        raw = f"{salt}:{password}:b2b_payment_salt"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _generate_token(user_id: str, user_type: str = "admin") -> str:
        payload = {
            "user_id": user_id,
            "user_type": user_type,
            "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    @staticmethod
    def _decode_token(token: str) -> dict:
        try:
            return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise BusinessException("TOKEN_EXPIRED", "登录已过期，请重新登录", 401)
        except jwt.InvalidTokenError:
            raise BusinessException("TOKEN_INVALID", "无效的令牌", 401)

    # ── 后台运营端登录 ──────────────────────────────────────

    @transaction.atomic
    def admin_login(self, account: str, password: str, ip: str = "") -> dict:
        """运营后台登录 — 用户名/邮箱+密码，返回 JWT Token 和用户信息。

        自动识别: 含 @ 按邮箱查询（大小写不敏感），否则按用户名查询。
        """
        is_email = "@" in account

        if is_email:
            account_lower = account.lower().strip()
            user = SystemUser.objects.filter(
                email__iexact=account_lower, is_deleted=False
            ).select_for_update().first()
        else:
            user = SystemUser.objects.filter(
                username=account, is_deleted=False
            ).select_for_update().first()

        if not user:
            OperationLog.objects.create(
                user=None,
                username=account,
                action=OperationLog.ActionType.LOGIN,
                resource="auth", resource_id="",
                detail={"reason": "user_not_found", "login_type": "email" if is_email else "username"},
                status=OperationLog.Status.FAILED,
                ip_address=ip,
            )
            raise BusinessException(
                "LOGIN_FAILED", "用户名/邮箱或密码错误", 401
            )

        if not user.is_active:
            raise BusinessException("ACCOUNT_DISABLED", "账号已停用", 403)

        if user.is_locked and user.locked_until and user.locked_until > timezone.now():
            raise BusinessException(
                "ACCOUNT_LOCKED",
                f"账号已锁定，请在 {user.locked_until.strftime('%H:%M')} 后重试",
                403,
            )

        if self._hash_password(password) != user.password_hash:
            user.login_failed_count += 1
            if user.login_failed_count >= MAX_LOGIN_ATTEMPTS:
                user.is_locked = True
                user.locked_until = timezone.now() + timedelta(minutes=LOCK_DURATION_MINUTES)
            user.save(update_fields=["login_failed_count", "is_locked", "locked_until"])

            OperationLog.objects.create(
                user=user, username=account,
                action=OperationLog.ActionType.LOGIN,
                resource="auth", resource_id=str(user.id),
                detail={"reason": "wrong_password", "attempt": user.login_failed_count},
                status=OperationLog.Status.FAILED,
                ip_address=ip,
            )
            raise BusinessException("LOGIN_FAILED", "用户名/邮箱或密码错误", 401)

        user.login_failed_count = 0
        user.is_locked = False
        user.locked_until = None
        user.last_login_at = timezone.now()
        user.last_login_ip = ip
        user.save(update_fields=[
            "login_failed_count", "is_locked", "locked_until",
            "last_login_at", "last_login_ip",
        ])

        token = self._generate_token(str(user.id), user_type="admin")

        OperationLog.objects.create(
            user=user, username=account,
            action=OperationLog.ActionType.LOGIN,
            resource="auth", resource_id=str(user.id),
            detail={"user_type": "admin", "login_type": "email" if is_email else "username"},
            status=OperationLog.Status.SUCCESS,
            ip_address=ip,
        )

        license_warnings = self._get_license_warnings()

        return {
            "token": token,
            "expires_in": TOKEN_EXPIRE_HOURS * 3600,
            "user": {
                "id": str(user.id),
                "username": user.username,
                "real_name": user.real_name,
                "phone": user.phone,
                "email": user.email,
                "roles": self.get_user_roles(str(user.id)),
                "permissions": self.get_user_permissions(str(user.id)),
            },
            "license_warnings": license_warnings,
        }

    @staticmethod
    def _get_license_warnings() -> list[dict]:
        """查询 30 天内牌照到期的活跃商户。"""
        today = date.today()
        cutoff = today + timedelta(days=30)
        expiring = Merchant.objects.filter(
            license_expiry_date__isnull=False,
            license_expiry_date__lte=cutoff,
            license_expiry_date__gte=today,
            status=Merchant.Status.ACTIVE,
        ).values("merchant_no", "merchant_name", "license_expiry_date").order_by("license_expiry_date")

        return [
            {
                "merchant_no": m["merchant_no"],
                "merchant_name": m["merchant_name"],
                "license_expiry_date": m["license_expiry_date"].isoformat(),
                "days_left": (m["license_expiry_date"] - today).days,
            }
            for m in expiring
        ]

    # ── 角色和权限查询 ──────────────────────────────────────

    def get_user_roles(self, user_id: str) -> list[str]:
        roles = UserRole.objects.filter(
            user_id=user_id, is_deleted=False
        ).select_related("role").values_list("role__code", flat=True)
        return list(roles)

    def get_user_permissions(self, user_id: str) -> list[str]:
        role_ids = UserRole.objects.filter(
            user_id=user_id, is_deleted=False
        ).values_list("role_id", flat=True)
        perms = RolePermission.objects.filter(
            role_id__in=role_ids, is_deleted=False
        ).select_related("permission").values_list("permission__code", flat=True)
        return list(perms.distinct())

    def has_permission(self, user_id: str, permission_code: str) -> bool:
        if self.has_role(user_id, "super_admin"):
            return True
        return permission_code in self.get_user_permissions(user_id)

    def has_role(self, user_id: str, role_code: str) -> bool:
        return role_code in self.get_user_roles(user_id)

    # ── 用户管理 ──────────────────────────────────────────

    def create_user(
        self, *, username: str, password: str, real_name: str,
        phone: str = "", email: str = "", role_codes: list[str] = None,
    ) -> SystemUser:
        if SystemUser.objects.filter(username=username).exists():
            raise BusinessException("USERNAME_EXISTS", f"用户名 {username} 已存在")

        user = SystemUser.objects.create(
            username=username,
            password_hash=self._hash_password(password),
            real_name=real_name,
            phone=phone,
            email=email,
        )

        if role_codes:
            roles = Role.objects.filter(code__in=role_codes)
            for role in roles:
                UserRole.objects.create(user=user, role=role)

        return user

    def reset_password(self, user: SystemUser, new_password: str):
        user.password_hash = self._hash_password(new_password)
        user.login_failed_count = 0
        user.is_locked = False
        user.locked_until = None
        user.save(update_fields=["password_hash", "login_failed_count", "is_locked", "locked_until"])

    def lock_user(self, user: SystemUser):
        user.is_locked = True
        user.locked_until = timezone.now() + timedelta(minutes=LOCK_DURATION_MINUTES)
        user.save(update_fields=["is_locked", "locked_until"])

    def unlock_user(self, user: SystemUser):
        user.is_locked = False
        user.locked_until = None
        user.login_failed_count = 0
        user.save(update_fields=["is_locked", "locked_until", "login_failed_count"])

    # ── 角色管理 ──────────────────────────────────────────

    def assign_roles(self, user: SystemUser, role_codes: list[str]):
        roles = Role.objects.filter(code__in=role_codes)
        existing = set(UserRole.objects.filter(
            user=user, is_deleted=False
        ).values_list("role__code", flat=True))
        for role in roles:
            if role.code not in existing:
                UserRole.objects.create(user=user, role=role)

    def grant_permission(self, role: Role, permission_codes: list[str]):
        perms = Permission.objects.filter(code__in=permission_codes)
        for perm in perms:
            # 使用 get_or_create 避免唯一约束冲突；若已软删则恢复
            rp, created = RolePermission.objects.get_or_create(
                role=role, permission=perm
            )
            if not created and rp.is_deleted:
                rp.is_deleted = False
                rp.save(update_fields=["is_deleted"])


class PermissionService:
    """权限校验服务 — 用于 API 层权限拦截。"""

    auth_service = AuthService()

    def check_permission(self, user_id: str, permission_code: str):
        if not self.auth_service.has_permission(user_id, permission_code):
            raise BusinessException(
                "PERMISSION_DENIED",
                f"缺少权限: {permission_code}",
                403,
            )

    def check_role(self, user_id: str, role_code: str):
        if not self.auth_service.has_role(user_id, role_code):
            raise BusinessException(
                "ROLE_DENIED",
                f"需要角色: {role_code}",
                403,
            )
