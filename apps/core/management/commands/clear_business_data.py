"""Clear all business data except OFAC/UN SanctionList.

Usage:
    python manage.py clear_business_data
    python manage.py clear_business_data --yes
"""

from django.core.management.base import BaseCommand

from apps.compliance.models import SanctionList
from apps.core.data_wipe import wipe_business_data


class Command(BaseCommand):
    help = "Wipe business/demo data; keep only SanctionList (OFAC/UN). Does not re-seed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip interactive confirmation",
        )

    def handle(self, *args, **options):
        kept = SanctionList.objects.count()
        if not options["yes"]:
            self.stdout.write(
                self.style.WARNING(
                    f"This will delete all business data and keep only SanctionList "
                    f"({kept} rows). Sessions/admin log/auth.User will also be cleared."
                )
            )
            confirm = input("Type 'yes' to continue: ").strip().lower()
            if confirm != "yes":
                self.stdout.write("Aborted.")
                return

        self.stdout.write(self.style.WARNING("Wiping business data (SanctionList only)..."))
        wipe_business_data(keep_risk_rating_limits=False, clear_framework_ephemera=True)
        remaining = SanctionList.objects.count()
        self.stdout.write(
            self.style.SUCCESS(f"Done. SanctionList preserved: {remaining} rows. No seed applied.")
        )
