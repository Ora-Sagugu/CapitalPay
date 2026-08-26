"""为所有尚未拥有 Nostro 账户的商户(客户)创建默认账户。

用于存量数据补齐：新注册商户已由信号自动开通账户，
本命令确保历史商户也都有账户。
"""
from django.core.management.base import BaseCommand
from apps.merchant.models import Merchant
from apps.merchant.services import ensure_merchant_account


class Command(BaseCommand):
    help = "Ensure every merchant (customer) has at least one Nostro account."

    def handle(self, *args, **options):
        created = 0
        merchants = Merchant.objects.filter(is_deleted=False)
        total = merchants.count()
        for merchant in merchants:
            if ensure_merchant_account(merchant) is not None:
                created += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Checked {total} merchant(s); created {created} default account(s)."
            )
        )
