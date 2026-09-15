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


class BuiltinOpsAccountTest(TestCase):
    """运营后台内置 admin，并保留其他运营账号。"""

    def setUp(self):
        self.svc = AuthService()
        Role.objects.create(code="super_admin", name="Super Admin", description="Full access", is_system=True)

    def test_ensure_builtin_account_and_login(self):
        user = self.svc.ensure_builtin_ops_account()
        self.assertEqual(user.username, "admin")
        result = self.svc.admin_login("admin", "123456", ip="127.0.0.1")
        self.assertEqual(result["user"]["username"], "admin")
        self.assertIn("super_admin", result["user"]["roles"])

    def test_ensure_creates_super_admin_role_when_missing(self):
        Role.objects.filter(code="super_admin").delete()
        user = self.svc.ensure_builtin_ops_account()
        self.assertTrue(Role.objects.filter(code="super_admin").exists())
        self.assertIn("super_admin", self.svc.get_user_roles(str(user.id)))

    def test_ensure_keeps_extra_ops_users(self):
        extra = self.svc.create_user(username="operator_x", password="Op@123456", real_name="Extra")
        self.svc.ensure_builtin_ops_account()
        extra.refresh_from_db()
        self.assertFalse(extra.is_deleted)
        self.assertTrue(extra.is_active)


class OpsUserApiGuardTest(TestCase):
    """Super Admin 可创建运营账号，但不能删除内置 admin。"""

    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.svc = AuthService()
        self.admin = self.svc.ensure_ops_rbac()["admin"]
        self.client.force_authenticate(self.admin)

    def test_create_ops_user_is_allowed(self):
        response = self.client.post(
            "/api/v1/admin/users/",
            {
                "username": "newbie",
                "password": "Pass@123",
                "real_name": "New Maker",
                "role_codes": ["maker"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(SystemUser.objects.filter(username="newbie").exists())

    def test_delete_builtin_admin_is_rejected(self):
        response = self.client.delete(f"/api/v1/admin/users/{self.admin.id}/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "OPS_ACCOUNT_PROTECTED")
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_deleted)


class FunctionAssignmentApiTest(TestCase):
    """职位勾选业务后，该角色才能访问对应接口。"""

    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.svc = AuthService()
        users = self.svc.ensure_ops_rbac()
        self.admin = users["admin"]
        self.maker = users["maker"]
        self.checker = users["checker"]
        self.maker_role = Role.objects.get(code="maker")
        self.admin_role = Role.objects.get(code="super_admin")

    def _login(self, username):
        result = self.svc.admin_login(username, "123456")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {result['token']}")
        return result

    def _pending_order(self):
        from datetime import timedelta
        from decimal import Decimal

        from django.utils import timezone

        from apps.merchant.models import Merchant
        from apps.payment.models import PaymentOrder

        merchant = Merchant.objects.create(
            merchant_no="RBACORD01",
            merchant_name="RBAC Order Merchant",
            status=Merchant.Status.ACTIVE,
        )
        return PaymentOrder.objects.create(
            order_no="RMT_RBAC_REVIEW",
            merchant_order_no="M_RBAC_REVIEW",
            unique_identification_no="UIN_RBAC_REVIEW",
            idempotency_key="IDEM_RBAC_REVIEW",
            merchant=merchant,
            amount=Decimal("10.00"),
            pay_method=PaymentOrder.PayMethod.WIRE_TRANSFER,
            expire_at=timezone.now() + timedelta(days=1),
            status=PaymentOrder.OrderStatus.PENDING_REVIEW,
        )

    def test_list_matrix_and_assign_capabilities(self):
        self._login("admin")
        listed = self.client.get("/api/v1/admin/functions/")
        self.assertEqual(listed.status_code, 200, listed.content)
        codes = [
            cap["code"]
            for group in listed.data["groups"]
            for cap in group["capabilities"]
        ]
        self.assertIn("feature:orders", codes)
        self.assertIn("feature:orders.approve", codes)
        self.assertIn("feature:agent_fees", codes)
        super_admin = next(r for r in listed.data["roles"] if r["code"] == "super_admin")
        self.assertTrue(super_admin["locked"])
        maker = next(r for r in listed.data["roles"] if r["code"] == "maker")
        assigned = self.client.put(
            f"/api/v1/admin/roles/{maker['id']}/capabilities/",
            {"capability_codes": ["feature:agent_fees"]},
            format="json",
        )
        self.assertEqual(assigned.status_code, 200, assigned.content)
        self.assertEqual(assigned.data["capability_codes"], ["feature:agent_fees"])

    def test_super_admin_capabilities_are_locked(self):
        self._login("admin")
        blocked = self.client.put(
            f"/api/v1/admin/roles/{self.admin_role.id}/capabilities/",
            {"capability_codes": ["feature:orders"]},
            format="json",
        )
        self.assertEqual(blocked.status_code, 400, blocked.content)
        self.assertEqual(blocked.data["code"], "SUPER_ADMIN_LOCKED")

    def test_maker_can_use_assigned_function_only(self):
        self.svc.set_role_capabilities(self.maker_role, ["feature:orders"])
        checker_role = Role.objects.get(code="checker")
        self.svc.set_role_capabilities(checker_role, ["feature:refunds"])

        maker = self._login("maker")
        self.assertIn("feature:orders", maker["user"]["permissions"])
        self.assertNotIn("feature:refunds", maker["user"]["permissions"])
        orders = self.client.get("/api/v1/admin/orders/")
        self.assertEqual(orders.status_code, 200, orders.content)
        refunds = self.client.get("/api/v1/admin/refunds/")
        self.assertEqual(refunds.status_code, 403)

        self._login("checker")
        self.assertEqual(self.client.get("/api/v1/admin/refunds/").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/admin/orders/").status_code, 403)

    def test_approve_code_required_for_order_review(self):
        order = self._pending_order()
        self.svc.set_role_capabilities(self.maker_role, ["feature:orders"])
        self._login("maker")
        self.assertEqual(self.client.get("/api/v1/admin/orders/").status_code, 200)
        denied = self.client.post(
            f"/api/v1/admin/orders/{order.order_no}/review/",
            {"action": "reject", "reason": "blocked by capability test"},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)

        self.svc.set_role_capabilities(
            self.maker_role, ["feature:orders", "feature:orders.approve"]
        )
        allowed = self.client.post(
            f"/api/v1/admin/orders/{order.order_no}/review/",
            {"action": "reject", "reason": "blocked by capability test"},
            format="json",
        )
        self.assertEqual(allowed.status_code, 200, allowed.content)

    def test_approve_only_still_opens_the_page(self):
        self.svc.set_role_capabilities(self.maker_role, ["feature:orders.approve"])
        self._login("maker")
        self.assertEqual(self.client.get("/api/v1/admin/orders/").status_code, 200)

    def test_agent_fee_capability(self):
        self.svc.set_role_capabilities(self.maker_role, ["feature:agent_fees"])
        self._login("maker")
        fees = self.client.get("/api/v1/admin/agent-commissions/")
        self.assertEqual(fees.status_code, 200, fees.content)
        self.assertEqual(self.client.get("/api/v1/admin/orders/").status_code, 403)

    def test_unassign_revokes_access(self):
        self.svc.set_role_capabilities(self.maker_role, ["feature:orders"])
        self._login("maker")
        self.assertEqual(self.client.get("/api/v1/admin/orders/").status_code, 200)
        self.svc.set_role_capabilities(self.maker_role, [])
        self._login("maker")
        self.assertEqual(self.client.get("/api/v1/admin/orders/").status_code, 403)

    def test_assign_roles_replaces(self):
        self.svc.assign_roles(self.maker, ["maker", "checker"])
        self.assertIn("maker", self.svc.get_user_roles(str(self.maker.id)))
        self.assertIn("checker", self.svc.get_user_roles(str(self.maker.id)))
        self.svc.assign_roles(self.maker, ["maker"])
        self.assertEqual(set(self.svc.get_user_roles(str(self.maker.id))), {"maker"})
