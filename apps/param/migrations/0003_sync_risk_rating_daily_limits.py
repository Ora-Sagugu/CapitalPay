from decimal import Decimal

from django.db import migrations


def sync_risk_rating_daily_limits(apps, schema_editor):
    RiskRatingLimit = apps.get_model("param", "RiskRatingLimit")
    for row in RiskRatingLimit.objects.all():
        expected = Decimal(row.max_single_amount) * int(row.daily_count)
        if row.daily_limit != expected:
            row.daily_limit = expected
            row.save(update_fields=["daily_limit", "updated_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("param", "0002_riskratinglimit"),
    ]

    operations = [
        migrations.RunPython(sync_risk_rating_daily_limits, migrations.RunPython.noop),
    ]
