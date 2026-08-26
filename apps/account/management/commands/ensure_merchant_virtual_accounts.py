"""管理命令 — 为所有缺少虚拟账户 (VA) 的客户补开默认 VA。

用法:
    python manage.py ensure_merchant_virtual_accounts
"""
from django.core.management.base import BaseCommand
from apps.merchant.models import Merchant
from apps.merchant.services import ensure_merchant_virtual_account


class Command(BaseCommand):
    help = "Ensure every merchant has at least one virtual account (VA)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--merchant-no",
            dest="merchant_no",
            default=None,
            help="只为指定商户号补开 VA (可选)",
        )

    def handle(self, *args, **options):
        merchant_no = options.get("merchant_no")
        qs = Merchant.objects.filter(is_deleted=False)
        if merchant_no:
            qs = qs.filter(merchant_no=merchant_no)

        created = 0
        skipped = 0
        for merchant in qs:
            va = ensure_merchant_virtual_account(merchant)
            if va:
                created += 1
                self.stdout.write(
                    f"[CREATED] VA {va.va_number} for {merchant.merchant_name} ({merchant.merchant_no})"
                )
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(f"Done. Created={created}, Skipped(already has VA)={skipped}")
        )
