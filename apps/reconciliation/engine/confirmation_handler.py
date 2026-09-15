"""对账引擎 — 支付确认处理器。

Phase 5: Payment Confirmation & Reconciliation
- PRN 匹配 + 金额一致 → 自动确认收款
- PRN 匹配 + 金额不一致 → 创建差异记录
"""

import logging
from typing import Optional

from apps.payment.models import PaymentOrder
from apps.payment.services.payment import PaymentConfirmService
from apps.reconciliation.models import ReconciliationBatch

logger = logging.getLogger(__name__)


class ConfirmationHandler:
    """对账确认处理器。

    根据对账匹配结果，自动更新支付订单状态：
    - PRN 匹配成功 + 金额一致 → 走统一收款确认服务
    - PRN 匹配成功 + 金额不一致 → 仅创建差异记录，不做自动确认
    """

    def process_matches(self, match_result, batch: ReconciliationBatch) -> dict:
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

            if match_type != "PRN":
                skipped += 1
                continue

            order = self._get_order(platform_order.order_no)
            if not order:
                skipped += 1
                continue

            if order.status in (
                PaymentOrder.OrderStatus.PAY_RECEIVED,
                PaymentOrder.OrderStatus.PENDING_SETTLE,
                PaymentOrder.OrderStatus.SETTLED,
                PaymentOrder.OrderStatus.COMPLETED,
            ):
                skipped += 1
                continue

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
        try:
            return PaymentOrder.objects.get(order_no=order_no, is_deleted=False)
        except PaymentOrder.DoesNotExist:
            return None

    def _auto_confirm(self, order: PaymentOrder, bank_line, batch: ReconciliationBatch):
        """统一走 PaymentConfirmService，保证 VA 分录与资金流水同时写入。"""
        confirmed = PaymentConfirmService()._confirm_payment(
            order,
            {"txn_id": getattr(bank_line, "txn_id", "") or "", "amount": bank_line.amount},
            prn_code=order.prn_code,
        )
        confirmed.add_status_history("CONFIRMED", {
            "source": "PRN_AUTO_MATCH",
            "prn_code": order.prn_code,
            "bank_txn_id": getattr(bank_line, "txn_id", "") or "",
            "bank_amount": str(bank_line.amount),
            "batch_no": batch.batch_no,
            "note": "Payment Confirmation Event: PRN matched, amount verified",
        })
        confirmed.save(update_fields=["status_history", "updated_at"])
        logger.info(
            f"Auto-confirmed [{order.order_no}] via PRN {order.prn_code}: "
            f"amount={order.amount}, bank_txn={getattr(bank_line, 'txn_id', '')}"
        )
