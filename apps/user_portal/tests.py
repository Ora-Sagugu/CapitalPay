"""用户端模块 — 单元测试。"""
from django.test import TestCase
from .models import EndUser, SmsCode, RefreshToken
from .services import UserService


class EndUserModelTest(TestCase):
    """终端用户模型测试。"""

    def test_create_user(self):
        user = EndUser.objects.create(
            phone="13800138000",
            password_hash="hashed",
            nickname="测试用户",
        )
        self.assertEqual(user.phone, "13800138000")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_verified)

    def test_phone_unique(self):
        EndUser.objects.create(phone="13800138001", password_hash="x")
        with self.assertRaises(Exception):
            EndUser.objects.create(phone="13800138001", password_hash="y")

    def test_soft_delete(self):
        user = EndUser.objects.create(phone="13800138002", password_hash="x")
        self.assertFalse(user.is_deleted)
        user.is_deleted = True
        user.save()
        self.assertTrue(user.is_deleted)


class UserServiceRegisterTest(TestCase):
    """用户注册服务测试。"""

    def setUp(self):
        self.svc = UserService()

    def test_register_success(self):
        result = self.svc.register(phone="13900000001", password="Test@123", sms_code="")
        self.assertIn("token", result)
        self.assertEqual(result["user"]["phone"], "139****0001")
        self.assertFalse(result["user"]["is_verified"])

    def test_register_duplicate_phone(self):
        self.svc.register(phone="13900000002", password="Test@123", sms_code="")
        with self.assertRaises(Exception) as ctx:
            self.svc.register(phone="13900000002", password="Test@123", sms_code="")
        self.assertEqual(ctx.exception.code, "PHONE_EXISTS")


class UserServiceLoginTest(TestCase):
    """用户登录服务测试。"""

    def setUp(self):
        self.svc = UserService()
        self.svc.register(phone="13900000005", password="Login@123", sms_code="")

    def test_login_by_password_success(self):
        result = self.svc.login_by_password("13900000005", "Login@123", ip="127.0.0.1")
        self.assertIn("token", result)
        self.assertIn("refresh_token", result)
        self.assertEqual(result["user"]["phone"], "139****0005")

    def test_login_wrong_password(self):
        with self.assertRaises(Exception) as ctx:
            self.svc.login_by_password("13900000005", "Wrong", ip="127.0.0.1")
        self.assertEqual(ctx.exception.code, "LOGIN_FAILED")

    def test_login_nonexistent_user(self):
        with self.assertRaises(Exception) as ctx:
            self.svc.login_by_password("13800000000", "Test@123", ip="127.0.0.1")
        self.assertEqual(ctx.exception.code, "LOGIN_FAILED")


class UserServiceProfileTest(TestCase):
    """用户资料服务测试。"""

    def setUp(self):
        self.svc = UserService()
        self.svc.register(phone="13900000010", password="Test@123", sms_code="")
        self.user = EndUser.objects.get(phone="13900000010")

    def test_get_profile(self):
        profile = self.svc.get_profile(self.user)
        self.assertEqual(profile["phone"], "139****0010")
        self.assertFalse(profile["is_verified"])

    def test_update_nickname(self):
        self.svc.update_profile(self.user, nickname="新昵称")
        self.user.refresh_from_db()
        self.assertEqual(self.user.nickname, "新昵称")

    def test_verify_identity(self):
        self.svc.verify_identity(self.user, real_name="张三", id_card="110101199001011234")
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)
        self.assertEqual(self.user.real_name, "张三")


class UserServiceSmsTest(TestCase):
    """短信验证码服务测试。"""

    def setUp(self):
        self.svc = UserService()

    def test_send_sms_code(self):
        result = self.svc.send_sms_code("13900000020", SmsCode.Scene.LOGIN)
        self.assertEqual(result["phone"], "13900000020")
        self.assertEqual(result["scene"], SmsCode.Scene.LOGIN)

    def test_send_sms_too_frequent(self):
        self.svc.send_sms_code("13900000021", SmsCode.Scene.LOGIN)
        with self.assertRaises(Exception) as ctx:
            self.svc.send_sms_code("13900000021", SmsCode.Scene.LOGIN)
        self.assertEqual(ctx.exception.code, "SMS_TOO_FREQUENT")


class UserServiceTokenTest(TestCase):
    """Token 相关测试。"""

    def setUp(self):
        self.svc = UserService()
        self.svc.register(phone="13900000030", password="Test@123", sms_code="")
        self.user = EndUser.objects.get(phone="13900000030")

    def test_refresh_token(self):
        result = self.svc.login_by_password("13900000030", "Test@123")
        new_result = self.svc.refresh_token(result["refresh_token"])
        self.assertIn("token", new_result)
        self.assertIn("refresh_token", new_result)
        self.assertNotEqual(result["refresh_token"], new_result["refresh_token"])

    def test_refresh_token_already_used(self):
        result = self.svc.login_by_password("13900000030", "Test@123")
        self.svc.refresh_token(result["refresh_token"])
        with self.assertRaises(Exception) as ctx:
            self.svc.refresh_token(result["refresh_token"])
        self.assertEqual(ctx.exception.code, "REFRESH_TOKEN_INVALID")
