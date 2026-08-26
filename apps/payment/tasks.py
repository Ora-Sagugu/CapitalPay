"""支付交易 — 同步任务（原 Celery）。"""
import logging

import requests
from django.utils import timezone

from apps.payment.models import PaymentOrder, RefundOrder

logger = logging.getLogger(__name__)


def notify_merchant(order_id: str):
    """通知商户支付结果；失败标记 FAILED，由定时命令重试。"""
    try:
        order = PaymentOrder.objects.get(id=order_id)
    except PaymentOrder.DoesNotExist:
        logger.warning(f"订单不存在: {order_id}")
        return

    if not order.notify_url:
        logger.info(f"订单无回调地址: {order.order_no}")
        return

    payload = {
        "order_no": order.order_no,
        "merchant_order_no": order.merchant_order_no,
        "status": order.status,
        "amount": str(order.amount),
        "fee_amount": str(order.fee_amount),
        "settle_amount": str(order.settle_amount),
        "pay_received_at": order.pay_received_at.isoformat() if order.pay_received_at else None,
        "bank_txn_id": order.bank_txn_id,
    }

    try:
        response = requests.post(
            order.notify_url,
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"},
        )
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")

        order.notify_status = "SUCCESS"
        order.notify_count += 1
        order.last_notify_at = timezone.now()
        order.save(update_fields=["notify_status", "notify_count", "last_notify_at"])
        logger.info(f"通知成功: {order.order_no}")

    except Exception as exc:
        order.notify_count += 1
        order.notify_status = "FAILED"
        order.last_notify_at = timezone.now()
        order.save(update_fields=["notify_status", "notify_count", "last_notify_at"])
        logger.error(f"通知失败: {order.order_no}, error={exc}")


def execute_refund_task(refund_id: str):
    """执行退款。"""
    from apps.payment.services.refund import RefundService

    try:
        refund = RefundOrder.objects.get(id=refund_id)
    except RefundOrder.DoesNotExist:
        logger.error(f"退款单不存在: {refund_id}")
        return

    service = RefundService()
    service.execute_refund(refund)
    logger.info(f"退款执行完成: {refund.refund_no}")


def close_expired_orders():
    """关闭过期订单。"""
    from apps.payment.services.close_order import CloseOrderService

    service = CloseOrderService()
    count = service.close_expired_orders()
    logger.info(f"过期订单关闭: {count} 笔")


def retry_failed_notifications():
    """重试失败的通知。"""
    failed_orders = PaymentOrder.objects.filter(
        notify_status="FAILED",
        notify_count__lt=10,
    ).exclude(notify_url__isnull=True).exclude(notify_url="")

    for order in failed_orders[:100]:
        notify_merchant(str(order.id))
