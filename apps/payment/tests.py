"""Payment 模块单元测试 — 预下单、支付确认、退款、关单。"""
from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.merchant.models import Merchant, MerchantFee
from apps.merchant.services import MerchantLifecycleService, MerchantService
from apps.payment.models import PaymentOrder, RefundOrder
from apps.payment.serializers import RemittanceSubmitSerializer
from apps.payment.services.pre_order import PreOrderService
from apps.payment.services.payment import PaymentConfirmService
from apps.payment.services.refund import RefundService
from apps.payment.services.close_order import CloseOrderService
from apps.core.exceptions import BusinessException, ErrorCode
from apps.core.utils import generate_idempotency_key


class PreOrderServiceTest(TestCase):
    """预下单服务测试。"""

    def setUp(self):
        self.service = PreOrderService()
        self.merchant_service = MerchantService()

        self.merchant = Merchant.objects.create(
            merchant_no="PAY_M001",
            merchant_name="支付测试商户",
            status=Merchant.Status.ACTIVE,
            api_key="ak_pay_001",
            api_secret="sk_pay_secret",
        )
        # 配置手续费: 0.3%, 最低 10, 封顶 500
        self.merchant_service.set_fee(self.merchant, {
            "product_type": MerchantFee.ProductType.WIRE_TRANSFER,
            "fee_model": MerchantFee.FeeModel.PERCENTAGE,
            "fee_rate": Decimal("0.003"),
            "min_fee": Decimal("10.00"),
            "max_fee": Decimal("500.00"),
            "effective_from": timezone.now().date(),
        })

    def test_create_pre_order_success(self):
        """正常创建预下单。"""
        order = self.service.create_pre_order(
            merchant_no="PAY_M001",
            merchant_order_no="MO001",
            amount=Decimal("100000.00"),
            pay_method="WIRE_TRANSFER",
            bank_code="CMB",
            user_id="U001",
            notify_url="https://example.com/callback",
        )
        self.assertEqual(order.merchant.merchant_no, "PAY_M001")
        self.assertEqual(order.amount, Decimal("100000.00"))
        # 100000 * 0.003 = 300
        self.assertEqual(order.fee_amount, Decimal("300.00"))
        self.assertEqual(order.settle_amount, Decimal("99700.00"))
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PENDING_PAY)
        self.assertTrue(order.order_no.startswith("P"))
        self.assertTrue(order.unique_identification_no.startswith("UIN"))
        self.assertEqual(len(order.status_history), 1)

    def test_create_pre_order_idempotency(self):
        """相同幂等键返回同一订单。"""
        key = generate_idempotency_key("test_")
        order1 = self.service.create_pre_order(
            merchant_no="PAY_M001",
            merchant_order_no="MO002",
            amount=Decimal("50000.00"),
            pay_method="WIRE_TRANSFER",
            idempotency_key=key,
        )
        order2 = self.service.create_pre_order(
            merchant_no="PAY_M001",
            merchant_order_no="MO002",
            amount=Decimal("50000.00"),
            pay_method="WIRE_TRANSFER",
            idempotency_key=key,
        )
        self.assertEqual(order1.id, order2.id)
        self.assertEqual(PaymentOrder.objects.count(), 1)

    def test_create_pre_order_inactive_merchant(self):
        """非活跃商户不能下单。"""
        MerchantLifecycleService().suspend(
            self.merchant,
            reason_code="TEST_SUSPEND",
            comment="test",
            actor="tests",
            source="TEST",
        )
        with self.assertRaises(BusinessException) as ctx:
            self.service.create_pre_order(
                merchant_no="PAY_M001",
                merchant_order_no="MO003",
                amount=Decimal("1000.00"),
                pay_method="WIRE_TRANSFER",
            )
        self.assertEqual(ctx.exception.code, ErrorCode.MERCHANT_INACTIVE)

    def test_create_pre_order_invalid_amount(self):
        """金额必须大于 0。"""
        with self.assertRaises(BusinessException) as ctx:
            self.service.create_pre_order(
                merchant_no="PAY_M001",
                merchant_order_no="MO004",
                amount=Decimal("0"),
                pay_method="WIRE_TRANSFER",
            )
        self.assertEqual(ctx.exception.code, "AMOUNT_INVALID")

    def test_create_pre_order_merchant_not_found(self):
        """商户不存在应抛异常。"""
        with self.assertRaises(BusinessException) as ctx:
            self.service.create_pre_order(
                merchant_no="NOT_EXIST",
                merchant_order_no="MO005",
                amount=Decimal("1000.00"),
                pay_method="WIRE_TRANSFER",
            )
        self.assertEqual(ctx.exception.code, ErrorCode.MERCHANT_NOT_FOUND)

    def test_create_pre_order_fee_calculation_with_min(self):
        """手续费低于最低值时取最低值。"""
        # 1000 * 0.003 = 3 < 10 → 取 10
        order = self.service.create_pre_order(
            merchant_no="PAY_M001",
            merchant_order_no="MO006",
            amount=Decimal("1000.00"),
            pay_method="WIRE_TRANSFER",
            bank_code="CMB",
        )
        self.assertEqual(order.fee_amount, Decimal("10.00"))

    def test_create_pre_order_fee_capped(self):
        """手续费超过封顶值时取封顶值。"""
        # 500000 * 0.003 = 1500 > 500 → 取 500
        order = self.service.create_pre_order(
            merchant_no="PAY_M001",
            merchant_order_no="MO007",
            amount=Decimal("500000.00"),
            pay_method="WIRE_TRANSFER",
            bank_code="CMB",
        )
        self.assertEqual(order.fee_amount, Decimal("500.00"))


class PaymentConfirmServiceTest(TestCase):
    """支付确认服务测试。"""

    def setUp(self):
        self.service = PaymentConfirmService()
        self.pre_order_service = PreOrderService()
        self.merchant_service = MerchantService()

        self.merchant = Merchant.objects.create(
            merchant_no="CONF_M001",
            merchant_name="确认测试商户",
            status=Merchant.Status.ACTIVE,
            api_key="ak_conf_001",
            api_secret="sk_conf_secret",
        )
        self.merchant_service.set_fee(self.merchant, {
            "product_type": MerchantFee.ProductType.WIRE_TRANSFER,
            "fee_model": MerchantFee.FeeModel.PERCENTAGE,
            "fee_rate": Decimal("0.003"),
            "effective_from": timezone.now().date(),
        })
        self.order = self.pre_order_service.create_pre_order(
            merchant_no="CONF_M001",
            merchant_order_no="MO_C001",
            amount=Decimal("50000.00"),
            pay_method="WIRE_TRANSFER",
            bank_code="CMB",
        )

    def test_auto_match_by_uin(self):
        """通过 UIN 自动匹配汇款。"""
        matched = self.service.auto_match_wire_transfer({
            "txn_id": "BANK_TX_001",
            "amount": Decimal("50000.00"),
            "remark": f"货款 {self.order.unique_identification_no} 已付",
            "txn_time": timezone.now(),
            "bank_code": "CMB",
        })
        self.assertIsNotNone(matched)
        self.assertEqual(matched.id, self.order.id)
        self.assertEqual(matched.status, PaymentOrder.OrderStatus.PAY_RECEIVED)
        self.assertEqual(matched.bank_txn_id, "BANK_TX_001")
        self.assertIsNotNone(matched.pay_received_at)

    def test_auto_match_by_amount(self):
        """通过金额模糊匹配（无 UIN）。"""
        matched = self.service.auto_match_wire_transfer({
            "txn_id": "BANK_TX_002",
            "amount": Decimal("50000.00"),
            "remark": "货款",
            "txn_time": timezone.now(),
            "bank_code": "CMB",
        })
        self.assertIsNotNone(matched)
        self.assertEqual(matched.status, PaymentOrder.OrderStatus.PAY_RECEIVED)

    def test_auto_match_no_match(self):
        """无匹配订单时返回 None。"""
        result = self.service.auto_match_wire_transfer({
            "txn_id": "BANK_TX_003",
            "amount": Decimal("99999.00"),  # 不匹配的金额
            "remark": "无备注",
            "txn_time": timezone.now(),
            "bank_code": "CMB",
        })
        self.assertIsNone(result)

    def test_confirm_amount_mismatch(self):
        """金额不一致应抛异常。"""
        with self.assertRaises(BusinessException) as ctx:
            self.service.auto_match_wire_transfer({
                "txn_id": "BANK_TX_004",
                "amount": Decimal("40000.00"),  # 不匹配
                "remark": self.order.unique_identification_no,
                "txn_time": timezone.now(),
                "bank_code": "CMB",
            })
        self.assertEqual(ctx.exception.code, ErrorCode.ORDER_AMOUNT_MISMATCH)

    def test_confirm_already_received(self):
        """已收款的订单不会被再次匹配。"""
        # 第一次确认
        self.service.auto_match_wire_transfer({
            "txn_id": "BANK_TX_005",
            "amount": Decimal("50000.00"),
            "remark": self.order.unique_identification_no,
            "txn_time": timezone.now(),
            "bank_code": "CMB",
        })
        # 第二次匹配不到（订单已不再是 PRE_CREATE 状态）
        result = self.service.auto_match_wire_transfer({
            "txn_id": "BANK_TX_006",
            "amount": Decimal("50000.00"),
            "remark": self.order.unique_identification_no,
            "txn_time": timezone.now(),
            "bank_code": "CMB",
        })
        self.assertIsNone(result)


class RefundServiceTest(TestCase):
    """退款服务测试。"""

    def setUp(self):
        self.service = RefundService()
        self.pre_order_service = PreOrderService()
        self.confirm_service = PaymentConfirmService()
        self.merchant_service = MerchantService()

        self.merchant = Merchant.objects.create(
            merchant_no="RF_M001",
            merchant_name="退款测试商户",
            status=Merchant.Status.ACTIVE,
            api_key="ak_rf_001",
            api_secret="sk_rf_secret",
        )
        self.merchant_service.set_fee(self.merchant, {
            "product_type": MerchantFee.ProductType.WIRE_TRANSFER,
            "fee_model": MerchantFee.FeeModel.FIXED,
            "fixed_fee": Decimal("10.00"),
            "effective_from": timezone.now().date(),
        })
        self.order = self.pre_order_service.create_pre_order(
            merchant_no="RF_M001",
            merchant_order_no="MO_RF001",
            amount=Decimal("100000.00"),
            pay_method="WIRE_TRANSFER",
            bank_code="CMB",
        )
        # 确认收款
        self.confirm_service.auto_match_wire_transfer({
            "txn_id": "BANK_RF_001",
            "amount": Decimal("100000.00"),
            "remark": self.order.unique_identification_no,
            "txn_time": timezone.now(),
            "bank_code": "CMB",
        })
        # 刷新订单对象（auto_match 修改了数据库中的状态）
        self.order.refresh_from_db()

    def test_request_refund_success(self):
        """正常发起退款。"""
        refund = self.service.request_refund(
            payment_order=self.order,
            refund_amount=Decimal("50000.00"),
            reason="部分退款测试",
        )
        self.assertEqual(refund.status, RefundOrder.RefundStatus.PENDING_REVIEW)
        self.assertEqual(refund.refund_amount, Decimal("50000.00"))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, PaymentOrder.OrderStatus.REFUNDING)

    def test_request_refund_exceed_amount(self):
        """退款超过订单金额应拒绝。"""
        self.service.request_refund(
            payment_order=self.order,
            refund_amount=Decimal("60000.00"),
            reason="第一次退款",
        )
        with self.assertRaises(BusinessException) as ctx:
            self.service.request_refund(
                payment_order=self.order,
                refund_amount=Decimal("50000.00"),  # 60000 + 50000 > 100000
                reason="超额退款",
            )
        self.assertEqual(ctx.exception.code, ErrorCode.REFUND_EXCEED_AMOUNT)

    def test_request_refund_invalid_amount(self):
        """退款金额必须大于 0。"""
        with self.assertRaises(BusinessException) as ctx:
            self.service.request_refund(
                payment_order=self.order,
                refund_amount=Decimal("0"),
                reason="无效退款",
            )
        self.assertEqual(ctx.exception.code, "REFUND_AMOUNT_INVALID")

    def test_request_refund_wrong_status(self):
        """非已收款订单不能退款。"""
        # 创建新订单但不确认收款
        new_order = self.pre_order_service.create_pre_order(
            merchant_no="RF_M001",
            merchant_order_no="MO_RF002",
            amount=Decimal("10000.00"),
            pay_method="WIRE_TRANSFER",
            bank_code="CMB",
        )
        CloseOrderService().close_order(new_order)
        new_order.refresh_from_db()
        with self.assertRaises(BusinessException) as ctx:
            self.service.request_refund(
                payment_order=new_order,
                refund_amount=Decimal("5000.00"),
                reason="测试",
            )
        self.assertEqual(ctx.exception.code, ErrorCode.ORDER_STATUS_INVALID)

    def test_approve_refund(self):
        """审核通过退款。"""
        refund = self.service.request_refund(
            payment_order=self.order,
            refund_amount=Decimal("50000.00"),
            reason="审核测试",
        )
        approved = self.service.approve_refund(refund, "admin")
        self.assertEqual(approved.status, RefundOrder.RefundStatus.APPROVED)
        self.assertEqual(approved.reviewed_by, "admin")
        self.assertIsNotNone(approved.reviewed_at)

    def test_reject_refund(self):
        """审核驳回退款。"""
        refund = self.service.request_refund(
            payment_order=self.order,
            refund_amount=Decimal("50000.00"),
            reason="驳回测试",
        )
        rejected = self.service.reject_refund(refund, "admin", "不符合退款条件")
        self.assertEqual(rejected.status, RefundOrder.RefundStatus.REJECTED)
        self.assertEqual(rejected.fail_reason, "不符合退款条件")
        # 原订单状态恢复
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, PaymentOrder.OrderStatus.PAY_RECEIVED)

    def test_approve_already_approved(self):
        """不能审核已审核的退款。"""
        refund = self.service.request_refund(
            payment_order=self.order,
            refund_amount=Decimal("50000.00"),
            reason="测试",
        )
        self.service.approve_refund(refund, "admin")
        with self.assertRaises(BusinessException):
            self.service.approve_refund(refund, "admin2")


class CloseOrderServiceTest(TestCase):
    """关单服务测试。"""

    def setUp(self):
        self.service = CloseOrderService()
        self.pre_order_service = PreOrderService()
        self.merchant_service = MerchantService()

        self.merchant = Merchant.objects.create(
            merchant_no="CL_M001",
            merchant_name="关单测试商户",
            status=Merchant.Status.ACTIVE,
            api_key="ak_cl_001",
            api_secret="sk_cl_secret",
        )
        self.merchant_service.set_fee(self.merchant, {
            "product_type": MerchantFee.ProductType.WIRE_TRANSFER,
            "fee_model": MerchantFee.FeeModel.FIXED,
            "fixed_fee": Decimal("5.00"),
            "effective_from": timezone.now().date(),
        })
        self.order = self.pre_order_service.create_pre_order(
            merchant_no="CL_M001",
            merchant_order_no="MO_CL001",
            amount=Decimal("20000.00"),
            pay_method="WIRE_TRANSFER",
            bank_code="CMB",
        )

    def test_close_pending_order(self):
        """待收款订单可以关闭。"""
        result = self.service.close_order(self.order)
        self.assertEqual(result.status, PaymentOrder.OrderStatus.CLOSED)
        self.assertIsNotNone(result.closed_at)

    def test_close_already_closed(self):
        """已关闭的订单不能重复关闭。"""
        self.service.close_order(self.order)
        with self.assertRaises(BusinessException) as ctx:
            self.service.close_order(self.order)
        self.assertEqual(ctx.exception.code, ErrorCode.ORDER_STATUS_INVALID)

    def test_close_paid_order(self):
        """已收款的订单不能关闭。"""
        # 先确认收款
        confirm_service = PaymentConfirmService()
        confirm_service.auto_match_wire_transfer({
            "txn_id": "BANK_CL_001",
            "amount": Decimal("20000.00"),
            "remark": self.order.unique_identification_no,
            "txn_time": timezone.now(),
            "bank_code": "CMB",
        })
        self.order.refresh_from_db()
        with self.assertRaises(BusinessException) as ctx:
            self.service.close_order(self.order)
        self.assertEqual(ctx.exception.code, ErrorCode.ORDER_STATUS_INVALID)


class RemittanceSubmitSerializerTest(TestCase):
    """提交序列化器只接收报价与收款信息，金额不得由客户端重算。"""

    def valid_data(self):
        return {
            "quote_id": "RQT20260830000000000001",
            "beneficiary_name": "张三",
            "beneficiary_bank": "中国银行",
            "beneficiary_account": "6217001234567890",
            "beneficiary_swift": "BKCHCNBJ",
            "beneficiary_address": "北京市朝阳区",
            "remittance_purpose": "货款",
        }

    def test_accepts_quote_and_beneficiary_payload(self):
        serializer = RemittanceSubmitSerializer(data=self.valid_data())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["quote_id"],
            "RQT20260830000000000001",
        )

    def test_quote_is_required(self):
        data = self.valid_data()
        data.pop("quote_id")
        serializer = RemittanceSubmitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("quote_id", serializer.errors)

    def test_required_beneficiary_fields(self):
        serializer = RemittanceSubmitSerializer(data={"quote_id": "RQT1"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("beneficiary_name", serializer.errors)
        self.assertIn("beneficiary_bank", serializer.errors)
        self.assertIn("beneficiary_account", serializer.errors)
