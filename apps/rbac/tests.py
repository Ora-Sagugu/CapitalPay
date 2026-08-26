"""RBAC 模块 — 单元测试。"""
from django.test import TestCase
from .models import SystemUser, Role, Permission, UserRole, RolePermission, OperationLog
from .services import AuthService


class RolePermissionModelTest(TestCase):
    """角色与权限模型测试。"""

    def setUp(self):
        self.role = Role.objects.create(code="test_role", name="测试角色", description="测试")
        self.perm = Permission.objects.create(
            code="merchant:view", name="查看商户",
            resource="merchant", action="view"
        )

    def test_create_role(self):
        self.assertEqual(self.role.code, "test_role")
        self.assertFalse(self.role.is_system)  # 非系统内置
        self.assertFalse(self.role.is_deleted)

    def test_create_permission(self):
        self.assertEqual(self.perm.code, "merchant:view")
        self.assertEqual(self.perm.resource, "merchant")
        self.assertEqual(self.perm.action, "view")

    def test_grant_permission(self):
        RolePermission.objects.create(role=self.role, permission=self.perm)
        count = RolePermission.objects.filter(role=self.role, is_deleted=False).count()
        self.assertEqual(count, 1)
        rp = RolePermission.objects.filter(role=self.role, is_deleted=False).first()
        self.assertEqual(rp.permission.code, "merchant:view")

    def test_role_permission_unique(self):
        RolePermission.objects.create(role=self.role, permission=self.perm)
        with self.assertRaises(Exception):
            RolePermission.objects.create(role=self.role, permission=self.perm)


class SystemUserModelTest(TestCase):
    """系统用户模型测试。"""

    def setUp(self):
        self.user = SystemUser.objects.create(
            username="operator1",
            password_hash="test_hash",
            real_name="张三",
        )

    def test_create_user(self):
        self.assertEqual(self.user.username, "operator1")
        self.assertTrue(self.user.is_active)
        self.assertEqual(self.user.login_failed_count, 0)

    def test_user_soft_delete(self):
        self.assertFalse(self.user.is_deleted)
        self.user.is_deleted = True
        self.user.save()
        self.assertTrue(self.user.is_deleted)


class AuthServiceTest(TestCase):
    """认证服务测试。"""

    def setUp(self):
        self.svc = AuthService()
        self.user = SystemUser.objects.create(
            username="ops1",
            password_hash=self.svc._hash_password("Secret@123"),
            real_name="李四",
        )

    def test_admin_login_success(self):
        result = self.svc.admin_login("ops1", "Secret@123", ip="127.0.0.1")
        self.assertIn("token", result)
        self.assertEqual(result["user"]["username"], "ops1")
        self.assertEqual(result["user"]["real_name"], "李四")

    def test_admin_login_wrong_password(self):
        with self.assertRaises(Exception) as ctx:
            self.svc.admin_login("ops1", "WrongPass", ip="127.0.0.1")
        self.assertEqual(ctx.exception.code, "LOGIN_FAILED")

    def test_admin_login_nonexistent_user(self):
        """不存在的用户名应返回 LOGIN_FAILED。"""
        with self.assertRaises(Exception) as ctx:
            self.svc.admin_login("nonexistent_user_xyz", "Secret@123", ip="127.0.0.1")
        self.assertEqual(ctx.exception.code, "LOGIN_FAILED")

    def test_password_hashing(self):
        h1 = self.svc._hash_password("p@ss")
        h2 = self.svc._hash_password("p@ss")
        self.assertEqual(h1, h2)  # deterministic

    def test_hash_password_different_inputs(self):
        h1 = self.svc._hash_password("pass1")
        h2 = self.svc._hash_password("pass2")
        self.assertNotEqual(h1, h2)


class UserRoleAssignmentTest(TestCase):
    """用户角色分配测试。"""

    def setUp(self):
        self.user = SystemUser.objects.create(
            username="assign_test", password_hash="x", real_name="王五"
        )
        self.role = Role.objects.create(code="finance_x", name="财务x", description="财务角色")

    def test_assign_role(self):
        UserRole.objects.create(user=self.user, role=self.role)
        count = UserRole.objects.filter(user=self.user, is_deleted=False).count()
        self.assertEqual(count, 1)

    def test_get_user_roles(self):
        UserRole.objects.create(user=self.user, role=self.role)
        svc = AuthService()
        roles = svc.get_user_roles(str(self.user.id))
        self.assertIn("finance_x", roles)


class OperationLogTest(TestCase):
    """操作日志测试。"""

    def setUp(self):
        self.user = SystemUser.objects.create(
            username="audit_test", password_hash="x", real_name="赵六"
        )

    def test_create_log(self):
        log = OperationLog.objects.create(
            user=self.user,
            action=OperationLog.ActionType.LOGIN,
            resource="auth",
            resource_id=str(self.user.id),
            status=OperationLog.Status.SUCCESS,
            ip_address="127.0.0.1",
        )
        self.assertEqual(log.action, OperationLog.ActionType.LOGIN)
        self.assertEqual(log.status, OperationLog.Status.SUCCESS)

    def test_log_immutable(self):
        """操作日志创建后不可修改。"""
        log = OperationLog.objects.create(
            user=self.user,
            username="audit_test",
            action=OperationLog.ActionType.LOGIN,
            resource="auth",
            resource_id=str(self.user.id),
            status=OperationLog.Status.SUCCESS,
        )
        with self.assertRaises(RuntimeError):
            log.status = OperationLog.Status.FAILED
            log.save()


class TokenGenerationTest(TestCase):
    """Token 生成测试。"""

    def test_generate_and_decode_token(self):
        svc = AuthService()
        token = svc._generate_token("test-id-123", user_type="admin")
        payload = svc._decode_token(token)
        self.assertEqual(payload["user_id"], "test-id-123")
        self.assertEqual(payload["user_type"], "admin")

    def test_decode_invalid_token(self):
        svc = AuthService()
        with self.assertRaises(Exception):
            svc._decode_token("invalid.token.here")
