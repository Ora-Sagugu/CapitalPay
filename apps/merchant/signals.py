"""商户信号 — 仅记录初始生命周期事件。"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Merchant, MerchantStatusEvent


@receiver(post_save, sender=Merchant)
def _record_initial_status(sender, instance, created, **kwargs):
    """新商户先保持待审核，不提前开通活动资金账户。"""
    if created:
        MerchantStatusEvent.objects.get_or_create(
            merchant=instance,
            from_status="",
            to_status=instance.status,
            reason_code="MERCHANT_CREATED",
            defaults={
                "comment": "商户记录已创建",
                "actor": "system",
                "source": "MODEL",
            },
        )
