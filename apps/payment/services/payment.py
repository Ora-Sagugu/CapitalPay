"""支付交易 — 支付确认服务。"""
from __future__ import annotations
import re
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.core.exceptions import BusinessException, ErrorCode
from ..models import PaymentOrder
from ..gateway import BankGatewayRouter


class PaymentConfirmService:
    """收款确认服务。

    匹配规则（优先级从高到低）:
    1. PRN 码精确匹配 — 附言中 PRN 与订单 prn_code 一致
    2. UIN 精确匹配 — 附言中 UIN 与订单唯一识别号一致
    3. 金额 + 时间窗口模糊匹配
    """

    UIN_PATTERN = re.compile(r"UIN\d{17}")
    PRN_PATTERN = re.compile(r"(?:PRN|prn)[:：\s]*(\d{6})|(?:^|\s)(\d{6})(?:\s|$)")

    def auto_match_wire_transfer(self, bank_statement_line: dict) -> PaymentOrder | None:
        """银行流水到达 → 自动匹配订单。

        Args:
            bank_statement_line: {
                "txn_id": str,       # 银行交易流水号
                "amount": Decimal,   # 金额
                "remark": str,       # 附言
                "txn_time": datetime,# 交易时间
                "bank_code": str,    # 银行编码
            }

        Returns:
            匹配到的 PaymentOrder，或 None
        """
        remark = bank_statement_line.get("remark", "")
        bank_amount = Decimal(str(bank_statement_line["amount"]))

        # ── 规则 1: PRN 精确匹配 ──
        prn_code = self._extract_prn(remark)
        if prn_code:
            order = PaymentOrder.objects.filter(
                prn_code=prn_code,
                status__in=[
                    PaymentOrder.OrderStatus.PENDING_REVIEW,
                    PaymentOrder.OrderStatus.PENDING_PAY,
                ],
            ).first()
            if order:
                return self._confirm_payment(order, bank_statement_line, prn_code)

        # ── 规则 2: UIN 精确匹配 ──
        uin_match = self.UIN_PATTERN.search(remark)
        if uin_match:
            uin = uin_match.group()
            order = PaymentOrder.objects.filter(
                unique_identification_no=uin,
                status=PaymentOrder.OrderStatus.PRE_CREATE,
            ).first()
            if order:
                return self._confirm_payment(order, bank_statement_line)

        # ── 规则 3: 金额 + 时间窗口模糊匹配 ──
        bank_time = bank_statement_line["txn_time"]
        candidates = PaymentOrder.objects.filter(
            amount=bank_amount,
            status=PaymentOrder.OrderStatus.PRE_CREATE,
            pay_method=PaymentOrder.PayMethod.WIRE_TRANSFER,
            created_at__gte=bank_time - timezone.timedelta(hours=24),
            created_at__lte=bank_time + timezone.timedelta(hours=1),
        ).order_by("created_at")

        if candidates.exists():
            return self._confirm_payment(candidates.first(), bank_statement_line)

        return None

    def manual_confirm(self, order_id: str, user_id: str, bank_txn_id: str = None) -> PaymentOrder:
        """用户手动关联汇款 → 确认收款。

        功能清单对应: 用户汇款确认
        """
        from apps.core.utils import generate_order_no as _unused  # keep import clean
        order = PaymentOrder.objects.get(id=order_id, user_id=user_id)

        if order.status != PaymentOrder.OrderStatus.PRE_CREATE:
            raise BusinessException(ErrorCode.ORDER_STATUS_INVALID)

        return self._confirm_payment(order, {"txn_id": bank_txn_id or ""})

    @staticmethod
    def _extract_prn(remark: str) -> str | None:
        """从附言中提取 6 位 PRN 码。"""
        if not remark:
            return None
        m = re.search(r"(?:PRN|prn)[:：\s]*(\d{6})", remark)
        if m:
            return m.group(1)
        standalone = re.findall(r"(?:^|\s)(\d{6})(?:\s|$)", remark)
        return standalone[0] if standalone else None

    @transaction.atomic
    def _confirm_payment(
        self, order: PaymentOrder, bank_info: dict, prn_code: str | None = None
    ) -> PaymentOrder:
        """执行收款确认 — 加行锁防止并发。

        Phase 5: Payment Confirmation & Reconciliation
        - 银行流水到达 → PRN 匹配 → 确认收款
        - 金额一致 → PAY_RECEIVED，创建交易记录
        - 通知 Payment Received (Status: CONFIRMED)
        """
        order = PaymentOrder.objects.select_for_update().get(pk=order.pk)

        # 可确认的状态：PRE_CREATE, PENDING_REVIEW, PENDING_PAY
        confirmable = {
            PaymentOrder.OrderStatus.PRE_CREATE,
            PaymentOrder.OrderStatus.PENDING_REVIEW,
            PaymentOrder.OrderStatus.PENDING_PAY,
        }
        if order.status not in confirmable:
            raise BusinessException(ErrorCode.ORDER_STATUS_INVALID)

        bank_txn_id = bank_info.get("txn_id", "")
        bank_amount = bank_info.get("amount", order.amount)

        # 金额校验
        if Decimal(str(bank_amount)) != order.amount:
            raise BusinessException(
                ErrorCode.ORDER_AMOUNT_MISMATCH,
                f"银行金额 {bank_amount} 与订单金额 {order.amount} 不一致",
            )

        now = timezone.now()
        order.status = PaymentOrder.OrderStatus.PAY_RECEIVED
        order.pay_received_at = now
        order.bank_txn_id = bank_txn_id
        extra = {"bank_txn_id": bank_txn_id}
        if prn_code:
            extra["prn_matched"] = True
            extra["prn_code"] = prn_code
        order.add_status_history(PaymentOrder.OrderStatus.PAY_RECEIVED, extra)
        order.save(update_fields=["status", "pay_received_at", "bank_txn_id", "status_history"])

        # ── 费用分账：手续费记入机构账户 ──
        self._credit_fees_to_agency(order)

        return order

    def _credit_fees_to_agency(self, order: PaymentOrder):
        """费用分账 — 将手续费记入机构账户。

        Phase 5: Credit Fees to Agency Account
        费用已随 PaymentOrder 创建时计算并存储，此处仅记录分账日志。
        """
        fee = order.fee_amount
        if fee and fee > 0:
            order.add_status_history("FEES_CREDITED", {
                "fee_amount": str(fee),
                "merchant": order.merchant.merchant_no,
                "note": "手续费已记入机构账户",
            })
            order.save(update_fields=["status_history", "updated_at"])
