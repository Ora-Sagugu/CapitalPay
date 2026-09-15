"""Import full OFAC SDN + UN consolidated sanctions from official online sources.

Usage:
    python manage.py import_all_sanctions --download --reset
    python manage.py import_all_sanctions --download
    python manage.py import_all_sanctions --download --dry-run
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.compliance.models import SanctionList


class Command(BaseCommand):
    help = "Import full OFAC SDN and UN consolidated sanctions from official sources"

    def add_arguments(self, parser):
        parser.add_argument(
            "--download",
            action="store_true",
            help="Download official OFAC SDN.CSV and UN consolidated.xml",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Clear existing OFAC/UN rows before import (manual full refresh)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse only; do not write to the database",
        )

    def handle(self, *args, **options):
        if not options["download"]:
            raise CommandError("Use --download to fetch official OFAC and UN lists")

        dry_run = options["dry_run"]
        reset = options["reset"]
        errors = []

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\nImporting full OFAC SDN list ..."
        ))
        try:
            ofac_kwargs = {
                "download": True,
                "max_entries": 0,
                "dry_run": dry_run,
            }
            if reset:
                ofac_kwargs["reset"] = True
            call_command("import_ofac_sdn", **ofac_kwargs)
        except Exception as exc:
            errors.append(f"OFAC: {exc}")
            self.stderr.write(self.style.ERROR(f"OFAC import failed: {exc}"))

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\nImporting full UN consolidated list ..."
        ))
        try:
            un_kwargs = {
                "download": True,
                "max_entries": 0,
                "dry_run": dry_run,
            }
            if reset:
                un_kwargs["reset"] = True
            call_command("import_un_sanctions", **un_kwargs)
        except Exception as exc:
            errors.append(f"UN: {exc}")
            self.stderr.write(self.style.ERROR(f"UN import failed: {exc}"))

        if errors:
            raise CommandError("; ".join(errors))

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run complete — no database changes"))
            return

        ofac_count = SanctionList.objects.filter(list_type="OFAC", is_active=True).count()
        un_count = SanctionList.objects.filter(list_type="UN", is_active=True).count()
        total = SanctionList.objects.filter(is_active=True).count()
        self.stdout.write(self.style.SUCCESS(
            f"\nSanctions import complete: OFAC={ofac_count:,}, UN={un_count:,}, total={total:,}"
        ))
