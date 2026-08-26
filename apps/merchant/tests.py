"""Merchant 模块单元测试 — 商户服务、手续费计算、KYC 加密。"""
from decimal import Decimal
from datetime import date

from django.test import TestCase

from apps.merchant.models import (
    Merchant, MerchantKYC, MerchantFee, MerchantSettlementAccount, MerchantPaymentProduct,
)
from apps.merchant.services import MerchantService
from apps.core.exceptions import BusinessException, ErrorCode
from apps.core.utils import decrypt_field


class MerchantModelTest(TestCase):
    """商户模型测试。"""

    def setUp(self):
        self.merchant = Merchant.objects.create(
            merchant_no="TEST_M001",
            merchant_name="测试商户有限公司",
            short_name="测试商户",
            api_key="ak_test_001",
            api_secret="sk_test_secret",
        )

    def test_merchant_str(self):
        """__str__ 应返回 商户名(商户编号)。"""
        self.assertEqual(str(self.merchant), "测试商户有限公司(TEST_M001)")

    def test_default_status_is_active(self):
        """新商户默认状态为 ACTIVE。"""
        self.assertEqual(self.merchant.status, Merchant.Status.ACTIVE)

    def test_default_is_deleted_false(self):
        """新商户默认未删除。"""
        self.assertFalse(self.merchant.is_deleted)

    def test_merchant_no_unique(self):
        """商户编号唯一约束。"""
        with self.assertRaises(Exception):
            Merchant.objects.create(
                merchant_no="TEST_M001",
                merchant_name="重复商户",
            )


class MerchantServiceTest(TestCase):
    """商户服务测试。"""

    def setUp(self):
        self.service = MerchantService()
        self.merchant = Merchant.objects.create(
            merchant_no="SVC_M001",
            merchant_name="服务测试商户",
            api_key="ak_svc_001",
            api_secret="sk_svc_secret",
        )

    # ── 查询 ──────────────────────────────────────────────

    def test_get_by_merchant_no_found(self):
        """按编号查到商户。"""
        found = self.service.get_by_merchant_no("SVC_M001")
        self.assertEqual(found.merchant_name, "服务测试商户")

    def test_get_by_merchant_no_not_found(self):
        """查不到商户应抛异常。"""
        with self.assertRaises(BusinessException) as ctx:
            self.service.get_by_merchant_no("NOT_EXIST")
        self.assertEqual(ctx.exception.code, ErrorCode.MERCHANT_NOT_FOUND)

    def test_get_by_api_key(self):
        """按 API Key 查商户。"""
        found = self.service.get_by_api_key("ak_svc_001")
        self.assertEqual(found.merchant_no, "SVC_M001")

    def test_list_active_merchants(self):
        """列出活跃商户。"""
        Merchant.objects.create(
            merchant_no="SVC_M002", merchant_name="商户2",
            status=Merchant.Status.SUSPENDED,
        )
        active = self.service.list_active_merchants()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].merchant_no, "SVC_M001")

    # ── KYC ───────────────────────────────────────────────

    def test_set_kyc_encrypts_sensitive_fields(self):
        """设置 KYC 时敏感字段应加密。"""
        kyc = self.service.set_kyc(self.merchant, {
            "legal_person": "张三",
            "id_number": "440301199001011234",
            "business_license": "91440300700123456X",
            "registered_capital": Decimal("5000000"),
            "established_date": date(2020, 1, 1),
        })
        # 数据库中存储的是密文
        self.assertNotEqual(kyc.id_number, "440301199001011234")
        self.assertNotEqual(kyc.business_license, "91440300700123456X")
        # 法人姓名不加密
        self.assertEqual(kyc.legal_person, "张三")

    def test_get_kyc_decrypts_sensitive_fields(self):
        """获取 KYC 时敏感字段应解密。"""
        self.service.set_kyc(self.merchant, {
            "legal_person": "李四",
            "id_number": "110108198503156789",
            "business_license": "91110108700245678X",
        })
        kyc_data = self.service.get_kyc(self.merchant)
        self.assertEqual(kyc_data["id_number"], "110108198503156789")
        self.assertEqual(kyc_data["business_license"], "91110108700245678X")
        self.assertEqual(kyc_data["legal_person"], "李四")

    def test_get_kyc_no_kyc(self):
        """没有 KYC 时返回基础信息。"""
        kyc_data = self.service.get_kyc(self.merchant)
        self.assertEqual(kyc_data["merchant_no"], "SVC_M001")
        self.assertNotIn("legal_person", kyc_data)

    # ── 手续费 ──────────────────────────────────────────────

    def test_calculate_fee_fixed(self):
        """固定手续费计算。"""
        self.service.set_fee(self.merchant, {
            "product_type": MerchantFee.ProductType.AUTHORIZED,
            "fee_model": MerchantFee.FeeModel.FIXED,
            "fixed_fee": Decimal("15.00"),
            "effective_from": date.today(),
        })
        result = self.service.calculate_fee(self.merchant, Decimal("1000.00"), "AUTHORIZED")
        self.assertEqual(result["fee_amount"], Decimal("15.00"))
        self.assertEqual(result["settle_amount"], Decimal("985.00"))
        self.assertEqual(result["fee_model"], "FIXED")

    def test_calculate_fee_percentage(self):
        """按比例手续费计算。"""
        self.service.set_fee(self.merchant, {
            "product_type": MerchantFee.ProductType.WIRE_TRANSFER,
            "fee_model": MerchantFee.FeeModel.PERCENTAGE,
            "fee_rate": Decimal("0.003"),  # 0.3%
            "min_fee": Decimal("10.00"),
            "max_fee": Decimal("500.00"),
            "effective_from": date.today(),
        })
        # 正常计算: 100000 * 0.003 = 300
        result = self.service.calculate_fee(self.merchant, Decimal("100000.00"), "WIRE_TRANSFER")
        self.assertEqual(result["fee_amount"], Decimal("300.000"))
        self.assertEqual(result["settle_amount"], Decimal("99700.00"))

    def test_calculate_fee_min_fee_applied(self):
        """手续费低于最低值时取最低值。"""
        self.service.set_fee(self.merchant, {
            "product_type": MerchantFee.ProductType.WIRE_TRANSFER,
            "fee_model": MerchantFee.FeeModel.PERCENTAGE,
            "fee_rate": Decimal("0.001"),  # 0.1%
            "min_fee": Decimal("50.00"),
            "effective_from": date.today(),
        })
        # 1000 * 0.001 = 1 < 50 → 取 50
        result = self.service.calculate_fee(self.merchant, Decimal("1000.00"), "WIRE_TRANSFER")
        self.assertEqual(result["fee_amount"], Decimal("50.00"))

    def test_calculate_fee_max_fee_capped(self):
        """手续费超过封顶值时取封顶值。"""
        self.service.set_fee(self.merchant, {
            "product_type": MerchantFee.ProductType.WIRE_TRANSFER,
            "fee_model": MerchantFee.FeeModel.PERCENTAGE,
            "fee_rate": Decimal("0.01"),  # 1%
            "max_fee": Decimal("500.00"),
            "effective_from": date.today(),
        })
        # 100000 * 0.01 = 1000 > 500 → 取 500
        result = self.service.calculate_fee(self.merchant, Decimal("100000.00"), "WIRE_TRANSFER")
        self.assertEqual(result["fee_amount"], Decimal("500.00"))

    def test_calculate_fee_not_configured(self):
        """未配置手续费应抛异常。"""
        with self.assertRaises(BusinessException) as ctx:
            self.service.calculate_fee(self.merchant, Decimal("1000.00"), "ONLINE_BANK")
        self.assertEqual(ctx.exception.code, ErrorCode.FEE_NOT_CONFIGURED)

    def test_get_current_fee_expired(self):
        """过期的手续费配置不生效。"""
        self.service.set_fee(self.merchant, {
            "product_type": MerchantFee.ProductType.WIRE_TRANSFER,
            "fee_model": MerchantFee.FeeModel.FIXED,
            "fixed_fee": Decimal("10.00"),
            "effective_from": date(2020, 1, 1),
            "effective_to": date(2020, 12, 31),
        })
        fee = self.service.get_current_fee(self.merchant, "WIRE_TRANSFER")
        self.assertIsNone(fee)

    # ── 结算账户 ────────────────────────────────────────────

    def test_set_settlement_account_encrypts_number(self):
        """结算账户号码应加密。"""
        account = self.service.set_settlement_account(self.merchant, {
            "bank_name": "招商银行",
            "account_name": "测试商户",
            "account_number": "6225880123456789",
            "is_default": True,
        })
        self.assertNotEqual(account.account_number, "6225880123456789")
        # 解密后正确
        self.assertEqual(decrypt_field(account.account_number), "6225880123456789")

    def test_only_one_default_account(self):
        """同一商户只能有一个默认账户。"""
        self.service.set_settlement_account(self.merchant, {
            "bank_name": "招商银行",
            "account_name": "商户",
            "account_number": "1111",
            "is_default": True,
        })
        self.service.set_settlement_account(self.merchant, {
            "bank_name": "工商银行",
            "account_name": "商户",
            "account_number": "2222",
            "is_default": True,
        })
        defaults = MerchantSettlementAccount.objects.filter(
            merchant=self.merchant, is_default=True
        )
        self.assertEqual(len(defaults), 1)
        self.assertEqual(defaults[0].bank_name, "工商银行")

    def test_get_default_settlement_account(self):
        """获取默认结算账户。"""
        self.service.set_settlement_account(self.merchant, {
            "bank_name": "建设银行",
            "account_name": "商户",
            "account_number": "3333",
            "is_default": True,
        })
        default = self.service.get_default_settlement_account(self.merchant)
        self.assertIsNotNone(default)
        self.assertEqual(default.bank_name, "建设银行")

    # ── 支付产品 ────────────────────────────────────────────

    def test_set_payment_product(self):
        """设置支付产品。"""
        product = self.service.set_payment_product(self.merchant, {
            "product_type": "WIRE_TRANSFER",
            "is_enabled": True,
            "max_single_amount": Decimal("1000000"),
        })
        self.assertTrue(product.is_enabled)
        self.assertEqual(product.max_single_amount, Decimal("1000000"))

    def test_set_payment_product_update(self):
        """更新已有支付产品配置。"""
        self.service.set_payment_product(self.merchant, {
            "product_type": "WIRE_TRANSFER",
            "is_enabled": True,
        })
        self.service.set_payment_product(self.merchant, {
            "product_type": "WIRE_TRANSFER",
            "is_enabled": False,
        })
        products = MerchantPaymentProduct.objects.filter(
            merchant=self.merchant, product_type="WIRE_TRANSFER"
        )
        self.assertEqual(len(products), 1)
        self.assertFalse(products[0].is_enabled)
