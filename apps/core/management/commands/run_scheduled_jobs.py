"""手动触发原定时任务。

用法:
    python manage.py run_scheduled_jobs --all
    python manage.py run_scheduled_jobs --job close_expired_orders
"""
from django.core.management.base import BaseCommand, CommandError

JOBS = {
    "close_expired_orders": ("apps.payment.tasks", "close_expired_orders"),
    "retry_failed_notifications": ("apps.payment.tasks", "retry_failed_notifications"),
    "run_daily_reconciliation": ("apps.reconciliation.tasks", "run_daily_reconciliation"),
    "run_settlement_fund_reconciliation": ("apps.reconciliation.tasks", "run_settlement_fund_reconciliation"),
    "check_nostro_balance": ("apps.reconciliation.tasks", "check_nostro_balance"),
    "run_daily_settlement": ("apps.settlement.tasks", "run_daily_settlement"),
    "generate_daily_reports": ("apps.report.tasks", "generate_daily_reports"),
    "suspend_expired_licenses": ("apps.merchant.tasks", "suspend_expired_licenses"),
    "refresh_sanction_lists": ("apps.compliance.tasks", "refresh_sanction_lists"),
}

# TEMPORARY: skipped while ENABLE_BANKING is False.
BANKING_JOBS = {
    "run_daily_reconciliation",
    "run_settlement_fund_reconciliation",
    "check_nostro_balance",
}


class Command(BaseCommand):
    help = "运行定时业务任务（关单、通知重试、对账、清算、执照过期等）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--job",
            choices=sorted(JOBS.keys()),
            help="运行指定任务",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="按顺序运行全部任务",
        )

    def handle(self, *args, **options):
        job = options.get("job")
        run_all = options.get("all")

        if not job and not run_all:
            raise CommandError("请指定 --job <name> 或 --all")

        from django.conf import settings

        names = list(JOBS.keys()) if run_all else [job]
        for name in names:
            if not getattr(settings, "ENABLE_BANKING", True) and name in BANKING_JOBS:
                self.stdout.write(self.style.WARNING(f"  skipped {name} (ENABLE_BANKING=False)"))
                continue
            module_path, attr = JOBS[name]
            self.stdout.write(self.style.MIGRATE_HEADING(f"Running {name}..."))
            module = __import__(module_path, fromlist=[attr])
            fn = getattr(module, attr)
            result = fn()
            if result is not None:
                self.stdout.write(f"  result={result}")
            self.stdout.write(self.style.SUCCESS(f"  done: {name}"))
