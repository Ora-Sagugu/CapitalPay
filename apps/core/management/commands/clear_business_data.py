"""Clear demo / test business data.

Keeps:
  - SanctionList (OFAC/UN)
  - BankChannel + RoutingRule (ops Channels)
  - Ops portal accounts (SystemUser / Role / Permission)

Usage:
    python manage.py clear_business_data
    python manage.py clear_business_data --yes
"""

from django.core.management.base import BaseCommand

from apps.compliance.models import SanctionList
from apps.core.data_wipe import wipe_business_data
from apps.rbac.models import SystemUser
from apps.routing.models import BankChannel, RoutingRule


class Command(BaseCommand):
    help = (
        "Wipe demo/test data; keep SanctionList, Channels (BankChannel/RoutingRule), "
        "and ops SystemUser accounts. Does not re-seed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip interactive confirmation",
        )

    def handle(self, *args, **options):
        sanctions = SanctionList.objects.count()
        channels = BankChannel.objects.count()
        routes = RoutingRule.objects.count()
        ops_users = SystemUser.objects.count()
        if not options["yes"]:
            self.stdout.write(
                self.style.WARNING(
                    "This will delete merchants, agents, portal users, orders, wallets, "
                    "and other test data.\n"
                    f"Preserved: SanctionList={sanctions}, BankChannel={channels}, "
                    f"RoutingRule={routes}, SystemUser={ops_users}."
                )
            )
            confirm = input("Type 'yes' to continue: ").strip().lower()
            if confirm != "yes":
                self.stdout.write("Aborted.")
                return

        self.stdout.write(
            self.style.WARNING(
                "Wiping test data (keep Channels, Sanctions, ops accounts)..."
            )
        )
        wipe_business_data(
            keep_risk_rating_limits=False,
            keep_channels=True,
            keep_ops_accounts=True,
            clear_framework_ephemera=True,
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Done. Preserved — "
                f"SanctionList={SanctionList.objects.count()}, "
                f"BankChannel={BankChannel.objects.count()}, "
                f"RoutingRule={RoutingRule.objects.count()}, "
                f"SystemUser={SystemUser.objects.count()}. No seed applied."
            )
        )
