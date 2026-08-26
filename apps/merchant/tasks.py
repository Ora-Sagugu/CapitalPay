"""商户执照过期自动限制交易。"""
import logging
from datetime import date

from django.utils import timezone

logger = logging.getLogger(__name__)


def suspend_expired_licenses():
    """执照已过期的 ACTIVE 商户自动暂停，禁止汇款。"""
    from apps.merchant.models import Merchant

    today = date.today()
    qs = Merchant.objects.filter(
        is_deleted=False,
        status=Merchant.Status.ACTIVE,
        license_expiry_date__lt=today,
    )
    count = 0
    for merchant in qs.iterator():
        merchant.status = Merchant.Status.SUSPENDED
        merchant.days_to_expiry = (merchant.license_expiry_date - today).days
        merchant.save(update_fields=["status", "days_to_expiry", "updated_at"])
        count += 1
        logger.info(
            "merchant.license_expired suspended=%s expiry=%s",
            merchant.merchant_no,
            merchant.license_expiry_date,
        )
    logger.info("suspend_expired_licenses done count=%s at=%s", count, timezone.now())
    return {"suspended": count}
