"""商户结果通知。"""
import logging

logger = logging.getLogger(__name__)


def trigger_order_notify(order) -> None:
    """订单进入终态/关键状态后通知商户。"""
    if not getattr(order, "notify_url", None):
        return
    try:
        from apps.payment.tasks import notify_merchant
        notify_merchant(str(order.id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("notify trigger failed order=%s err=%s", getattr(order, "order_no", ""), exc)
