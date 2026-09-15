"""Core 模块单元测试 — 工具函数、加密、签名。"""
from django.test import TestCase
from apps.core.utils import (
    encrypt_field, decrypt_field,
    sign_params, verify_signature,
    generate_order_no, generate_uin, generate_batch_no,
    generate_idempotency_key,
)
from apps.core.models import AuditLog
from apps.core.exceptions import BusinessException, ErrorCode


class EncryptDecryptTest(TestCase):
    """加密解密测试。"""

    def test_encrypt_then_decrypt_roundtrip(self):
        """加密后解密应返回原文。"""
        plaintext = "6225880123456789"
        encrypted = encrypt_field(plaintext)
        self.assertNotEqual(encrypted, plaintext)
        self.assertTrue(len(encrypted) > 0)
        decrypted = decrypt_field(encrypted)
        self.assertEqual(decrypted, plaintext)

    def test_encrypt_empty_string(self):
        """空字符串加密应返回空字符串。"""
        self.assertEqual(encrypt_field(""), "")
        self.assertEqual(decrypt_field(""), "")

    def test_encrypt_chinese_text(self):
        """中文字符串加密解密。"""
        text = "深圳市环球贸易有限公司"
        encrypted = encrypt_field(text)
        decrypted = decrypt_field(encrypted)
        self.assertEqual(decrypted, text)

    def test_encrypt_different_inputs_different_outputs(self):
        """不同输入应产生不同密文。"""
        e1 = encrypt_field("123456")
        e2 = encrypt_field("789012")
        self.assertNotEqual(e1, e2)

    def test_encrypt_same_input_different_outputs(self):
        """相同输入每次加密应产生不同密文（Fernet 特性）。"""
        e1 = encrypt_field("123456")
        e2 = encrypt_field("123456")
        self.assertNotEqual(e1, e2)
        # 但解密后应一致
        self.assertEqual(decrypt_field(e1), decrypt_field(e2))


class SignatureTest(TestCase):
    """签名验签测试。"""

    def test_sign_and_verify_success(self):
        """正确签名应验签通过。"""
        params = {"merchant_no": "M001", "amount": "100.00", "order_no": "PAY001"}
        secret = "my_secret_key"
        signature = sign_params(params, secret)
        self.assertTrue(len(signature) == 64)  # HMAC-SHA256 = 64 hex chars
        self.assertTrue(verify_signature(params, signature, secret))

    def test_verify_wrong_signature(self):
        """错误签名应验签失败。"""
        params = {"merchant_no": "M001", "amount": "100.00"}
        secret = "my_secret_key"
        wrong_signature = "0" * 64
        self.assertFalse(verify_signature(params, wrong_signature, secret))

    def test_verify_tampered_params(self):
        """篡改参数后签名应失效。"""
        params = {"merchant_no": "M001", "amount": "100.00"}
        secret = "my_secret_key"
        signature = sign_params(params, secret)
        # 篡改金额
        tampered_params = {"merchant_no": "M001", "amount": "999.00"}
        self.assertFalse(verify_signature(tampered_params, signature, secret))

    def test_signature_order_independent(self):
        """签名与参数顺序无关（内部排序）。"""
        secret = "key"
        params_a = {"a": "1", "b": "2", "c": "3"}
        params_b = {"c": "3", "a": "1", "b": "2"}
        sig_a = sign_params(params_a, secret)
        sig_b = sign_params(params_b, secret)
        self.assertEqual(sig_a, sig_b)


class OrderNoGenerationTest(TestCase):
    """流水号生成测试。"""

    def test_generate_order_no_prefix(self):
        """订单号应以指定前缀开头。"""
        no = generate_order_no("P")
        self.assertTrue(no.startswith("P"))
        no2 = generate_order_no("R")
        self.assertTrue(no2.startswith("R"))

    def test_generate_order_no_unique(self):
        """连续生成的订单号应唯一。"""
        nos = {generate_order_no("T") for _ in range(100)}
        self.assertEqual(len(nos), 100)

    def test_generate_uin_format(self):
        """UIN 应以 UIN 开头。"""
        uin = generate_uin()
        self.assertTrue(uin.startswith("UIN"))
        self.assertTrue(len(uin) > 10)

    def test_generate_batch_no(self):
        """批次号应以前缀开头。"""
        no = generate_batch_no("B")
        self.assertTrue(no.startswith("B"))

    def test_generate_idempotency_key(self):
        """幂等键应为 UUID 格式。"""
        key = generate_idempotency_key()
        self.assertEqual(len(key), 32)
        key_with_prefix = generate_idempotency_key("seed_")
        self.assertTrue(key_with_prefix.startswith("seed_"))


class AuditLogTest(TestCase):
    """审计日志测试。"""

    def test_create_audit_log(self):
        """创建审计日志。"""
        log = AuditLog.objects.create(
            operator="admin",
            action="CREATE",
            resource_type="PaymentOrder",
            resource_id="123",
            after_snapshot={"amount": "100.00"},
        )
        self.assertIsNotNone(log.id)
        self.assertEqual(log.operator, "admin")
        self.assertEqual(log.action, "CREATE")
        self.assertIsNotNone(log.created_at)

    def test_audit_log_cannot_update(self):
        """审计日志不可修改。"""
        log = AuditLog.objects.create(
            operator="admin", action="CREATE",
            resource_type="Test", resource_id="1",
        )
        log.action = "UPDATE"
        with self.assertRaises(RuntimeError):
            log.save()


class BusinessExceptionTest(TestCase):
    """业务异常测试。"""

    def test_exception_attributes(self):
        """异常应携带错误码和消息。"""
        exc = BusinessException(ErrorCode.MERCHANT_NOT_FOUND, "The customer does not exist", 404)
        self.assertEqual(exc.code, ErrorCode.MERCHANT_NOT_FOUND)
        self.assertEqual(exc.message, "The customer does not exist")
        self.assertEqual(exc.http_status, 404)

    def test_exception_default_message(self):
        """未提供消息时使用错误码。"""
        exc = BusinessException("CUSTOM_ERROR")
        self.assertEqual(exc.message, "CUSTOM_ERROR")
