"""对账差异预警。"""
from __future__ import annotations
import logging

from django.conf import settings
from django.utils import timezone

from apps.reconciliation.models import ReconAlert, ReconAlertConfig, ReconciliationBatch

logger = logging.getLogger(__name__)


def fire_recon_alerts(batch: ReconciliationBatch, diff_count: int):
    """对账产生差异后创建站内预警，并按配置投递 Webhook / 邮件。"""
    if diff_count <= 0:
        return None

    config = ReconAlertConfig.get_config()
    severity = (
        ReconAlert.Severity.CRITICAL if diff_count >= 10 else ReconAlert.Severity.WARNING
    )
    title = f"对账差异预警 {batch.batch_no}"
    summary = (
        f"银行 {batch.bank_code} 对账日 {batch.reconciliation_date} "
        f"共 {diff_count} 笔差异（批次 {batch.batch_no}）"
    )
    alert = ReconAlert.objects.create(
        batch=batch,
        severity=severity,
        title=title,
        summary=summary,
        channel=ReconAlert.Channel.IN_APP,
        status=ReconAlert.AlertStatus.OPEN,
    )

    if not config.enabled:
        return alert

    payload = {
        "event": "recon.diff",
        "batch_no": batch.batch_no,
        "bank_code": batch.bank_code,
        "reconciliation_date": str(batch.reconciliation_date),
        "diff_count": diff_count,
        "severity": severity,
        "title": title,
        "summary": summary,
    }

    if config.webhook_url:
        _deliver_webhook(alert, config.webhook_url, payload)
    if config.email:
        _deliver_email(alert, config.email, title, summary)
    return alert


def _deliver_webhook(alert: ReconAlert, url: str, payload: dict):
    import requests

    try:
        resp = requests.post(url, json=payload, timeout=8)
        alert.channel = ReconAlert.Channel.WEBHOOK
        alert.sent_at = timezone.now()
        if resp.status_code >= 400:
            alert.delivery_error = f"HTTP {resp.status_code}"[:256]
        alert.save(update_fields=["channel", "sent_at", "delivery_error", "updated_at"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("recon alert webhook failed: %s", exc)
        alert.delivery_error = str(exc)[:256]
        alert.save(update_fields=["delivery_error", "updated_at"])


def _deliver_email(alert: ReconAlert, to_email: str, title: str, summary: str):
    host = getattr(settings, "EMAIL_HOST", "") or ""
    if not host:
        return
    try:
        from django.core.mail import send_mail
        send_mail(
            subject=title,
            message=summary,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None) or "noreply@localhost",
            recipient_list=[to_email],
            fail_silently=True,
        )
        alert.channel = ReconAlert.Channel.EMAIL
        alert.sent_at = timezone.now()
        alert.save(update_fields=["channel", "sent_at", "updated_at"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("recon alert email failed: %s", exc)
        alert.delivery_error = str(exc)[:256]
        alert.save(update_fields=["delivery_error", "updated_at"])
