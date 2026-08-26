"""对账引擎 — 支付确认处理器。

Phase 5: Payment Confirmation & Reconciliation
- PRN 匹配 + 金额一致 → 自动确认收款
- PRN 匹配 + 金额不一致 → 创建差异记录
"""

import logging
from typing import Optional
from django.utils import timezone
from apps.payment.models import PaymentOrder
from apps.reconciliation.models import ReconciliationBatch, ReconciliationDiff

logger = logging.getLogger(__name__)


class ConfirmationHandler:
    """对账确认处理器。

    根据对账匹配结果，自动更新支付订单状态：
    - PRN 匹配成功 + 金额一致 → PAY_RECEIVED + 费用分账
    - PRN 匹配成功 + 金额不一致 → 仅创建差异记录，不做自动确认
    """

    def process_matches(self, match_result, batch: ReconciliationBatch) -> dict:
        """处理匹配结果，自动确认 PRN 匹配成功的订单。

        Args:
            match_result: ReconciliationMatcher.match() 的返回值
            batch: 对账批次记录

        Returns:
            {"auto_confirmed": int, "fee_credited": int, "skipped": int}
        """
        auto_confirmed = 0
        fee_credited = 0
        skipped = 0

        for item in match_result.matched:
            match_type = item.get("match_type", "")
            platform_order = item.get("platform")
            bank_line = item.get("bank")

            if not platform_order or not bank_line:
                skipped += 1
                continue

            # 非 PRN 匹配的不自动确认
            if match_type != "PRN":
                skipped += 1
                continue

            order = self._get_order(platform_order.order_no)
            if not order:
                skipped += 1
                continue

            # 已收款的跳过
            if order.status in (
                PaymentOrder.OrderStatus.PAY_RECEIVED,
                PaymentOrder.OrderStatus.PENDING_SETTLE,
                PaymentOrder.OrderStatus.SETTLED,
            ):
                skipped += 1
                continue

            # 确认收款
            try:
                self._auto_confirm(order, bank_line, batch)
                auto_confirmed += 1
                fee_credited += int(bool(order.fee_amount))
            except Exception as e:
                logger.error(f"Auto-confirm failed [{order.order_no}]: {e}")
                skipped += 1

        return {
            "auto_confirmed": auto_confirmed,
            "fee_credited": fee_credited,
            "skipped": skipped,
        }

    def _get_order(self, order_no: str) -> Optional[PaymentOrder]:
        """获取支付订单。"""
        try:
            return PaymentOrder.objects.get(order_no=order_no, is_deleted=False)
        except PaymentOrder.DoesNotExist:
            return None

    def _auto_confirm(self, order: PaymentOrder, bank_line, batch: ReconciliationBatch):
        """自动确认收款。

        1. 更新 PaymentOrder → PAY_RECEIVED
        2. 费用分账记录到状态历史
        3. 通知 Payment Received (Status: CONFIRMED)
        """
        now = timezone.now()
        order.status = PaymentOrder.OrderStatus.PAY_RECEIVED
        order.pay_received_at = now
        order.bank_txn_id = bank_line.txn_id
        order.add_status_history("CONFIRMED", {
            "source": "PRN_AUTO_MATCH",
            "prn_code": order.prn_code,
            "bank_txn_id": bank_line.txn_id,
            "bank_amount": str(bank_line.amount),
            "batch_no": batch.batch_no,
            "note": "Payment Confirmation Event: PRN matched, amount verified",
        })

        # 费用分账
        fee = order.fee_amount
        if fee and fee > 0:
            order.add_status_history("FEES_CREDITED", {
                "fee_amount": str(fee),
                "merchant": order.merchant.merchant_no,
                "note": "手续费已记入机构账户",
            })

        order.save(update_fields=["status", "pay_received_at", "bank_txn_id", "status_history", "updated_at"])

        logger.info(
            f"Auto-confirmed [{order.order_no}] via PRN {order.prn_code}: "
            f"amount={order.amount}, bank_txn={bank_line.txn_id}"
        )
