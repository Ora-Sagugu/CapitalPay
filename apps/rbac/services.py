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
from .functions import (
    APPROVE_BACKFILL_PAIRS,
    ASSIGNABLE_ROLE_CODES,
    FEATURE_CODES,
    FUNCTION_BY_CODE,
    LEGACY_ROLE_MAP,
    OPS_CAPABILITIES,
    OPS_FUNCTIONS,
    OPS_ROLES,
    RETIRED_ROLE_CODES,
    SYSTEM_ROLE_CODES,
    codes_for_page,
)
from .models import SystemUser, Role, Permission, UserRole, RolePermission, OperationLog

OPS_DEMO_PASSWORD = "123456"
OPS_DEMO_USERS = (
    ("admin", "Administrator", "super_admin", "admin@capitalpay.com"),
    ("maker", "Maker", "maker", "maker@capitalpay.com"),
    ("checker", "Checker", "checker", "checker@capitalpay.com"),
    ("authoriser", "Authoriser", "authoriser", "authoriser@capitalpay.com"),
)


MAX_LOGIN_ATTEMPTS = 5
LOCK_DURATION_MINUTES = 30
TOKEN_EXPIRE_HOURS = 8
OPS_BUILTIN_USERNAME = "admin"
OPS_BUILTIN_PASSWORD = "123456"


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
            raise BusinessException("TOKEN_EXPIRED", "The session has expired. Authenticate again.", 401)
        except jwt.InvalidTokenError:
            raise BusinessException("TOKEN_INVALID", "The authentication token is invalid", 401)

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
                "LOGIN_FAILED", "The identifier or password is incorrect", 401
            )

        if not user.is_active:
            raise BusinessException("ACCOUNT_DISABLED", "The account has been disabled", 403)

        if user.is_locked and user.locked_until and user.locked_until > timezone.now():
            raise BusinessException(
                "ACCOUNT_LOCKED",
                f"The account is locked. Retry after {user.locked_until.strftime('%H:%M')}",
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
            raise BusinessException("LOGIN_FAILED", "The identifier or password is incorrect", 401)

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

    def has_page_access(self, user_id: str, page_code: str) -> bool:
        if self.has_role(user_id, "super_admin"):
            return True
        held = set(self.get_user_permissions(user_id))
        return any(code in held for code in codes_for_page(page_code))

    def has_role(self, user_id: str, role_code: str) -> bool:
        return role_code in self.get_user_roles(user_id)

    # ── 用户管理 ──────────────────────────────────────────

    def is_builtin_ops_user(self, user: SystemUser) -> bool:
        return (user.username or "") == OPS_BUILTIN_USERNAME

    def ensure_builtin_ops_account(self) -> SystemUser:
        """Ensure the built-in admin account exists. Extra ops users are kept."""
        self.ensure_ops_rbac()
        return SystemUser.objects.get(username=OPS_BUILTIN_USERNAME)

    def ensure_ops_rbac(self) -> dict:
        """Idempotent catalog: 4 roles, feature permissions, demo accounts."""
        self._ensure_feature_permissions()
        self._ensure_system_roles()
        self._migrate_legacy_roles()
        users = {}
        for username, real_name, role_code, email in OPS_DEMO_USERS:
            users[username] = self._ensure_demo_user(
                username=username,
                real_name=real_name,
                role_code=role_code,
                email=email,
            )
        return users

    def ensure_ops_rbac_if_needed(self):
        existing = set(
            Permission.objects.filter(
                code__in=FEATURE_CODES, is_deleted=False
            ).values_list("code", flat=True)
        )
        if existing != set(FEATURE_CODES):
            self.ensure_ops_rbac()

    def _ensure_feature_permissions(self):
        wanted = set(FEATURE_CODES)
        created_codes = set()
        for item in OPS_CAPABILITIES:
            action = item.get("action") or "view"
            perm, created = Permission.objects.get_or_create(
                code=item["code"],
                defaults={
                    "name": item["name"],
                    "resource": item["resource"],
                    "action": action,
                    "description": item["path"],
                    "is_deleted": False,
                },
            )
            updates = []
            if perm.name != item["name"]:
                perm.name = item["name"]
                updates.append("name")
            if perm.resource != item["resource"]:
                perm.resource = item["resource"]
                updates.append("resource")
            if perm.action != action:
                perm.action = action
                updates.append("action")
            if perm.description != item["path"]:
                perm.description = item["path"]
                updates.append("description")
            if perm.is_deleted:
                perm.is_deleted = False
                updates.append("is_deleted")
            if updates:
                perm.save(update_fields=updates + ["updated_at"])
            if created:
                created_codes.add(item["code"])

        self._backfill_approve_from_view(created_codes)

        stale = Permission.objects.filter(is_deleted=False).exclude(code__in=wanted)
        stale_ids = list(stale.values_list("id", flat=True))
        if stale_ids:
            stale.update(is_deleted=True)
            RolePermission.objects.filter(permission_id__in=stale_ids, is_deleted=False).update(
                is_deleted=True
            )

    def _backfill_approve_from_view(self, created_codes: set[str]):
        """Copy existing page grants onto newly created approve codes once."""
        if not created_codes:
            return
        for view_code, approve_code in APPROVE_BACKFILL_PAIRS:
            if approve_code not in created_codes:
                continue
            view_perm = Permission.objects.filter(code=view_code, is_deleted=False).first()
            approve_perm = Permission.objects.filter(code=approve_code, is_deleted=False).first()
            if not view_perm or not approve_perm:
                continue
            role_ids = RolePermission.objects.filter(
                permission=view_perm, is_deleted=False, role__is_deleted=False
            ).values_list("role_id", flat=True)
            for role_id in role_ids:
                rp, created = RolePermission.objects.get_or_create(
                    role_id=role_id, permission=approve_perm
                )
                if not created and rp.is_deleted:
                    rp.is_deleted = False
                    rp.save(update_fields=["is_deleted"])

    def _ensure_system_roles(self):
        for spec in OPS_ROLES:
            role, created = Role.objects.get_or_create(
                code=spec["code"],
                defaults={
                    "name": spec["name"],
                    "description": spec["description"],
                    "is_system": True,
                    "is_deleted": False,
                },
            )
            updates = []
            if role.name != spec["name"]:
                role.name = spec["name"]
                updates.append("name")
            if role.description != spec["description"]:
                role.description = spec["description"]
                updates.append("description")
            if not role.is_system:
                role.is_system = True
                updates.append("is_system")
            if role.is_deleted:
                role.is_deleted = False
                updates.append("is_deleted")
            if updates:
                role.save(update_fields=updates + ["updated_at"])

    def _migrate_legacy_roles(self):
        for old_code, new_code in LEGACY_ROLE_MAP.items():
            old = Role.objects.filter(code=old_code).first()
            new = Role.objects.filter(code=new_code, is_deleted=False).first()
            if not old or not new:
                continue
            for ur in UserRole.objects.filter(role=old, is_deleted=False):
                existing = UserRole.objects.filter(user=ur.user, role=new).first()
                if existing:
                    if existing.is_deleted:
                        existing.is_deleted = False
                        existing.save(update_fields=["is_deleted"])
                else:
                    UserRole.objects.create(user=ur.user, role=new)
                ur.is_deleted = True
                ur.save(update_fields=["is_deleted"])

        Role.objects.filter(code__in=RETIRED_ROLE_CODES, is_deleted=False).update(is_deleted=True)

    def _ensure_demo_user(self, *, username: str, real_name: str, role_code: str, email: str):
        user = SystemUser.objects.filter(username=username).first()
        if user:
            updates = []
            if username == OPS_BUILTIN_USERNAME:
                user.password_hash = self._hash_password(OPS_DEMO_PASSWORD)
                updates.append("password_hash")
            if user.is_deleted:
                user.is_deleted = False
                updates.append("is_deleted")
            if not user.is_active:
                user.is_active = True
                updates.append("is_active")
            if user.is_locked:
                user.is_locked = False
                user.locked_until = None
                user.login_failed_count = 0
                updates.extend(["is_locked", "locked_until", "login_failed_count"])
            if not user.real_name:
                user.real_name = real_name
                updates.append("real_name")
            if email and not user.email:
                user.email = email
                updates.append("email")
            if updates:
                user.save(update_fields=updates)
        else:
            user = self.create_user(
                username=username,
                password=OPS_DEMO_PASSWORD,
                real_name=real_name,
                email=email,
                role_codes=[role_code],
            )
        if not self.has_role(str(user.id), role_code):
            current = self.get_user_roles(str(user.id))
            if role_code not in current:
                current.append(role_code)
            self.assign_roles(user, current)
        return user

    def create_user(
        self, *, username: str, password: str, real_name: str,
        phone: str = "", email: str = "", role_codes: list[str] = None,
    ) -> SystemUser:
        if SystemUser.objects.filter(username=username).exists():
            raise BusinessException("USERNAME_EXISTS", f"The user identifier {username} already exists")

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
        wanted = list(role_codes or [])
        if self.is_builtin_ops_user(user) and "super_admin" not in wanted:
            wanted.append("super_admin")
        wanted_set = set(wanted)
        current = {
            ur.role.code: ur
            for ur in UserRole.objects.filter(user=user).select_related("role")
        }
        for code, ur in current.items():
            if code in wanted_set:
                if ur.is_deleted:
                    ur.is_deleted = False
                    ur.save(update_fields=["is_deleted"])
            elif not ur.is_deleted:
                ur.is_deleted = True
                ur.save(update_fields=["is_deleted"])
        missing = wanted_set - set(current.keys())
        if missing:
            for role in Role.objects.filter(code__in=missing, is_deleted=False):
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

    def list_capability_groups(self) -> list[dict]:
        grouped = []
        current_group = None
        bucket = None
        for item in OPS_CAPABILITIES:
            group_key = item["group"]
            if bucket is None or current_group != group_key:
                current_group = group_key
                bucket = {
                    "group": item["group"],
                    "group_name": item["group_name"],
                    "capabilities": [],
                }
                grouped.append(bucket)
            bucket["capabilities"].append({
                "code": item["code"],
                "name": item["name"],
                "action": item["action"],
                "path": item["path"],
                "page": item["page"],
                "resource": item["resource"],
            })
        return grouped

    def list_role_matrix(self) -> dict:
        role_caps: dict[str, list[str]] = {code: [] for code in ASSIGNABLE_ROLE_CODES}
        rows = RolePermission.objects.filter(
            is_deleted=False,
            role__code__in=ASSIGNABLE_ROLE_CODES,
            role__is_deleted=False,
            permission__code__in=FEATURE_CODES,
            permission__is_deleted=False,
        ).values_list("role__code", "permission__code")
        for role_code, perm_code in rows:
            if perm_code not in role_caps[role_code]:
                role_caps[role_code].append(perm_code)

        roles_by_code = {
            role.code: role
            for role in Role.objects.filter(code__in=SYSTEM_ROLE_CODES, is_deleted=False)
        }
        roles = []
        for spec in OPS_ROLES:
            role = roles_by_code.get(spec["code"])
            locked = spec["code"] == "super_admin"
            codes = list(FEATURE_CODES) if locked else list(role_caps.get(spec["code"], []))
            roles.append({
                "id": str(role.id) if role else "",
                "code": spec["code"],
                "name": spec["name"],
                "description": spec["description"],
                "locked": locked,
                "capability_codes": codes,
                "capability_count": len(codes),
            })
        return {
            "roles": roles,
            "groups": self.list_capability_groups(),
            "assignable_roles": list(ASSIGNABLE_ROLE_CODES),
        }

    def list_functions(self) -> list[dict]:
        """Legacy function→roles grouping kept for older clients."""
        role_map = {code: [] for code in FEATURE_CODES}
        rows = RolePermission.objects.filter(
            is_deleted=False,
            role__code__in=ASSIGNABLE_ROLE_CODES,
            role__is_deleted=False,
            permission__code__in=FEATURE_CODES,
            permission__is_deleted=False,
        ).values_list("permission__code", "role__code")
        for perm_code, role_code in rows:
            if role_code not in role_map[perm_code]:
                role_map[perm_code].append(role_code)
        grouped = []
        current_group = None
        bucket = None
        for item in OPS_FUNCTIONS:
            entry = {
                **item,
                "role_codes": role_map.get(item["code"], []),
            }
            group_key = item["group"]
            if bucket is None or current_group != group_key:
                current_group = group_key
                bucket = {
                    "group": item["group"],
                    "group_name": item["group_name"],
                    "functions": [],
                }
                grouped.append(bucket)
            bucket["functions"].append(entry)
        return grouped

    def set_role_capabilities(self, role: Role, capability_codes: list[str]) -> list[str]:
        if role.code == "super_admin":
            raise BusinessException(
                "SUPER_ADMIN_LOCKED",
                "Super Admin always has every business and cannot be changed",
                400,
            )
        if role.code not in ASSIGNABLE_ROLE_CODES:
            raise BusinessException(
                "ROLE_NOT_ASSIGNABLE",
                f"Capabilities cannot be assigned to role {role.code}",
                400,
            )
        wanted = {code for code in (capability_codes or []) if code in FEATURE_CODES}
        for perm in Permission.objects.filter(code__in=FEATURE_CODES, is_deleted=False):
            rp = RolePermission.objects.filter(role=role, permission=perm).first()
            if perm.code in wanted:
                if rp:
                    if rp.is_deleted:
                        rp.is_deleted = False
                        rp.save(update_fields=["is_deleted"])
                else:
                    RolePermission.objects.create(role=role, permission=perm)
            elif rp and not rp.is_deleted:
                rp.is_deleted = True
                rp.save(update_fields=["is_deleted"])
        return sorted(wanted)

    def set_function_roles(self, feature_code: str, role_codes: list[str]) -> list[str]:
        spec = FUNCTION_BY_CODE.get(feature_code)
        if not spec:
            raise BusinessException("FUNCTION_NOT_FOUND", f"Unknown function {feature_code}", 404)
        perm = Permission.objects.filter(code=feature_code, is_deleted=False).first()
        if not perm:
            raise BusinessException("FUNCTION_NOT_FOUND", f"Unknown function {feature_code}", 404)
        wanted = {code for code in (role_codes or []) if code in ASSIGNABLE_ROLE_CODES}
        for role in Role.objects.filter(code__in=ASSIGNABLE_ROLE_CODES, is_deleted=False):
            rp = RolePermission.objects.filter(role=role, permission=perm).first()
            if role.code in wanted:
                if rp:
                    if rp.is_deleted:
                        rp.is_deleted = False
                        rp.save(update_fields=["is_deleted"])
                else:
                    RolePermission.objects.create(role=role, permission=perm)
            elif rp and not rp.is_deleted:
                rp.is_deleted = True
                rp.save(update_fields=["is_deleted"])
        return sorted(wanted)


class PermissionService:
    """权限校验服务 — 用于 API 层权限拦截。"""

    auth_service = AuthService()

    def check_permission(self, user_id: str, permission_code: str):
        if not self.auth_service.has_permission(user_id, permission_code):
            raise BusinessException(
                "PERMISSION_DENIED",
                f"The authenticated principal is not authorised for permission {permission_code}",
                403,
            )

    def check_page_access(self, user_id: str, page_code: str):
        if not self.auth_service.has_page_access(user_id, page_code):
            raise BusinessException(
                "PERMISSION_DENIED",
                f"The authenticated principal is not authorised for permission {page_code}",
                403,
            )

    def check_role(self, user_id: str, role_code: str):
        if not self.auth_service.has_role(user_id, role_code):
            raise BusinessException(
                "ROLE_DENIED",
                f"The authenticated principal does not hold the required role {role_code}",
                403,
            )
