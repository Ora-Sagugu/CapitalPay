"""支付交易 — 关单服务。"""
from django.db import transaction
from django.utils import timezone
from apps.core.exceptions import BusinessException, ErrorCode
from ..models import PaymentOrder


class CloseOrderService:
    """订单关闭服务。"""

    @transaction.atomic
    def close_order(self, order: PaymentOrder, reason: str = "") -> PaymentOrder:
        """关闭订单 — 仅预创建/待收款状态可关闭。"""
        closeable_statuses = [
            PaymentOrder.OrderStatus.PRE_CREATE,
        ]

        if order.status not in closeable_statuses:
            raise BusinessException(ErrorCode.ORDER_STATUS_INVALID, "当前订单状态不可关闭")

        order.status = PaymentOrder.OrderStatus.CLOSED
        order.closed_at = timezone.now()
        order.add_status_history(PaymentOrder.OrderStatus.CLOSED, {"reason": reason})
        order.save(update_fields=["status", "closed_at", "status_history"])

        return order

    def close_expired_orders(self) -> int:
        """批量关闭过期订单 — 由 Celery 定时任务调用。"""
        expired = PaymentOrder.objects.filter(
            status=PaymentOrder.OrderStatus.PRE_CREATE,
            expire_at__lte=timezone.now(),
        )
        count = expired.count()

        for order in expired:
            try:
                self.close_order(order, reason="订单已过期")
            except BusinessException:
                pass

        return count
