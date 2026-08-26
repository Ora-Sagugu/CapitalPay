"""商户信号 — 注册时自动开通默认账户。"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Merchant
from .services import ensure_merchant_account, ensure_merchant_virtual_account


@receiver(post_save, sender=Merchant)
def _create_account_on_register(sender, instance, created, **kwargs):
    """新商户(客户)注册入库后，自动为其创建 Nostro 账户与虚拟账户 (VA)。"""
    if created:
        ensure_merchant_account(instance)
        ensure_merchant_virtual_account(instance)
