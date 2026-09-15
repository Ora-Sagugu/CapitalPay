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


def build_cashier_url(order: PaymentOrder) -> str:
    base = getattr(settings, "CASHIER_BASE_URL", "http://localhost:1027/pay")
    return f"{base.rstrip('/')}/{order.order_no}?uin={order.unique_identification_no}"


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
        """
        if idempotency_key:
            existing = PaymentOrder.objects.filter(
                idempotency_key=idempotency_key,
                is_deleted=False,
            ).first()
            if existing:
                return existing

        merchant = self.merchant_service.get_by_merchant_no(merchant_no)
        if merchant.status != merchant.Status.ACTIVE:
            raise BusinessException(ErrorCode.MERCHANT_INACTIVE)
        from datetime import date as date_cls
        if merchant.license_expiry_date and merchant.license_expiry_date < date_cls.today():
            raise BusinessException(
                ErrorCode.MERCHANT_INACTIVE,
                "Merchant business license has expired; remittance is restricted",
            )

        if amount <= 0:
            raise BusinessException("AMOUNT_INVALID", "The amount must be greater than zero")

        self._assert_product_allowed(merchant, pay_method, amount)

        fee_result = self.merchant_service.calculate_fee(merchant, amount, pay_method)

        order_no = generate_order_no()
        uin = generate_uin()
        bank_code = bank_code or self._select_route(amount, currency, order_no)

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
            status=PaymentOrder.OrderStatus.PENDING_PAY,
            expire_at=timezone.now() + timezone.timedelta(minutes=expire_minutes),
            idempotency_key=idempotency_key or uuid.uuid4().hex,
            notify_url=notify_url,
        )
        order.add_status_history(PaymentOrder.OrderStatus.PENDING_PAY, {"from": "PRE_ORDER"})
        order.save()

        self._log_route(order)
        self._kickoff_pay_method(order)
        return order

    def _assert_product_allowed(self, merchant, pay_method: str, amount: Decimal):
        from apps.merchant.models import MerchantPaymentProduct

        products = MerchantPaymentProduct.objects.filter(merchant=merchant, is_deleted=False)
        if not products.exists():
            return
        product = products.filter(product_type=pay_method, is_enabled=True).first()
        if not product:
            raise BusinessException("PRODUCT_DISABLED", "This payment product has not been enabled")
        if product.max_single_amount and amount > product.max_single_amount:
            raise BusinessException("AMOUNT_EXCEED_LIMIT", "The amount exceeds the single-instruction limit")

    def _select_route(self, amount, currency, order_no) -> str:
        try:
            from apps.routing.services import RoutingService
            channel = RoutingService.route_select(float(amount), currency or "CNY", "CN")
            if channel:
                return channel.bank_code
        except Exception:
            pass
        return None

    def _log_route(self, order: PaymentOrder):
        try:
            from apps.routing.models import BankChannel, RoutingLog
            channel = BankChannel.objects.filter(bank_code=order.bank_code).first() if order.bank_code else None
            RoutingLog.objects.create(
                order_no=order.order_no,
                channel=channel,
                amount=order.amount,
                currency=order.currency,
                result=RoutingLog.Result.SUCCESS if channel else RoutingLog.Result.FAILED,
                request_data={"pay_method": order.pay_method, "bank_code": order.bank_code},
            )
        except Exception:
            pass

    def _kickoff_pay_method(self, order: PaymentOrder):
        from ..gateway import BankGatewayRouter

        if order.pay_method == PaymentOrder.PayMethod.ONLINE_BANK:
            gateway = BankGatewayRouter.get_gateway(order.bank_code)
            result = gateway.pay(order)
            extra = {"gateway": result}
            order.add_status_history("GATEWAY_PAY", extra)
            order.save(update_fields=["status_history", "updated_at"])
            return

        if order.pay_method == PaymentOrder.PayMethod.AUTHORIZED and order.user_id:
            from apps.account.services import AccountService
            accounts = AccountService().get_user_accounts(order.user_id)
            if not accounts:
                return
            gateway = BankGatewayRouter.get_gateway(order.bank_code)
            result = gateway.pay(order)
            from .payment import PaymentConfirmService
            PaymentConfirmService()._confirm_payment(
                order,
                {"txn_id": result.get("txn_id") or f"AUTH_{order.order_no}", "amount": order.amount},
            )
