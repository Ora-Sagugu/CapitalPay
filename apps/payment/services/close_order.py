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
            PaymentOrder.OrderStatus.PENDING_PAY,
        ]

        if order.status not in closeable_statuses:
            raise BusinessException(ErrorCode.ORDER_STATUS_INVALID, "The current instruction status does not permit closure")

        order.status = PaymentOrder.OrderStatus.CLOSED
        order.closed_at = timezone.now()
        order.add_status_history(PaymentOrder.OrderStatus.CLOSED, {"reason": reason})
        order.save(update_fields=["status", "closed_at", "status_history"])

        from .notify import trigger_order_notify
        trigger_order_notify(order)
        return order

    def close_expired_orders(self) -> int:
        """批量关闭过期订单 — 由定时任务调用。"""
        expired = PaymentOrder.objects.filter(
            status__in=[
                PaymentOrder.OrderStatus.PRE_CREATE,
                PaymentOrder.OrderStatus.PENDING_PAY,
            ],
            expire_at__lte=timezone.now(),
        )
        count = expired.count()

        for order in expired:
            try:
                self.close_order(order, reason="The order has expired")
            except BusinessException:
                pass

        return count
