"""支付交易 — 预下单服务。"""
import uuid
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from apps.core.exceptions import BusinessException, ErrorCode
from apps.merchant.services import MerchantService
from apps.core.utils import generate_order_no, generate_uin
from ..models import PaymentOrder


class PreOrderService:
    """预下单服务。

    功能清单对应:
        - 预下单 (预下单创建、生成、返回收银台URL)
        - 状态变更为待收款
    """

    def __init__(self):
        self.merchant_service = MerchantService()

    @transaction.atomic
    def create_pre_order(
        self,
        *,
        merchant_no: str,
        merchant_order_no: str,
        amount: Decimal,
        currency: str = "CNY",
        pay_method: str,
        bank_code: str = None,
        user_id: str = None,
        notify_url: str = None,
        idempotency_key: str = None,
    ) -> PaymentOrder:
        """创建预下单。

        幂等性: 相同 idempotency_key 返回已有订单。

        Returns:
            PaymentOrder 实例
        """
        # ── 1. 幂等检查 ──
        if idempotency_key:
            existing = PaymentOrder.objects.filter(
                idempotency_key=idempotency_key,
                is_deleted=False,
            ).first()
            if existing:
                return existing

        # ── 2. 查询商户 ──
        merchant = self.merchant_service.get_by_merchant_no(merchant_no)
        if merchant.status != merchant.Status.ACTIVE:
            raise BusinessException(ErrorCode.MERCHANT_INACTIVE)
        from datetime import date as date_cls
        if merchant.license_expiry_date and merchant.license_expiry_date < date_cls.today():
            raise BusinessException(
                ErrorCode.MERCHANT_INACTIVE,
                "Merchant business license has expired; remittance is restricted",
            )

        # ── 3. 金额校验 ──
        if amount <= 0:
            raise BusinessException("AMOUNT_INVALID", "金额必须大于0")

        # ── 4. 计算手续费 ──
        fee_result = self.merchant_service.calculate_fee(merchant, amount, pay_method)

        # ── 5. 生成订单号 ──
        order_no = generate_order_no()
        uin = generate_uin()

        # ── 6. 创建订单 ──
        expire_minutes = getattr(settings, "ORDER_EXPIRE_MINUTES", 30)
        order = PaymentOrder(
            order_no=order_no,
            merchant_order_no=merchant_order_no,
            unique_identification_no=uin,
            merchant=merchant,
            user_id=user_id,
            currency=currency,
            amount=amount,
            fee_amount=fee_result["fee_amount"],
            settle_amount=fee_result["settle_amount"],
            pay_method=pay_method,
            bank_code=bank_code,
            status=PaymentOrder.OrderStatus.PRE_CREATE,
            expire_at=timezone.now() + timezone.timedelta(minutes=expire_minutes),
            idempotency_key=idempotency_key or uuid.uuid4().hex,
            notify_url=notify_url,
        )
        order.add_status_history(PaymentOrder.OrderStatus.PRE_CREATE)
        order.save()

        return order
