import uuid
from decimal import Decimal

import django.core.validators
from django.db import migrations, models


def seed_risk_rating_limits(apps, schema_editor):
    RiskRatingLimit = apps.get_model("param", "RiskRatingLimit")
    defaults = (
        ("LOW", Decimal("10000.00"), 10, Decimal("3.00")),
        ("MEDIUM", Decimal("5000.00"), 5, Decimal("2.00")),
        ("HIGH", Decimal("1000.00"), 3, Decimal("1.00")),
        ("BLOCKED", Decimal("0.00"), 0, Decimal("0.00")),
    )
    for risk_level, single, count, daily in defaults:
        RiskRatingLimit.objects.get_or_create(
            risk_level=risk_level,
            defaults={
                "max_single_amount": single,
                "daily_count": count,
                "daily_limit": daily,
            },
        )


def unseed_risk_rating_limits(apps, schema_editor):
    RiskRatingLimit = apps.get_model("param", "RiskRatingLimit")
    RiskRatingLimit.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("param", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RiskRatingLimit",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "risk_level",
                    models.CharField(
                        choices=[
                            ("LOW", "Low"),
                            ("MEDIUM", "Medium"),
                            ("HIGH", "High"),
                            ("BLOCKED", "Blocked"),
                        ],
                        max_length=16,
                        unique=True,
                        verbose_name="风险等级",
                    ),
                ),
                ("max_single_amount", models.DecimalField(decimal_places=2, default=0, max_digits=18, verbose_name="单笔限额")),
                (
                    "daily_count",
                    models.IntegerField(
                        default=0,
                        validators=[django.core.validators.MinValueValidator(0)],
                        verbose_name="每日笔数",
                    ),
                ),
                ("daily_limit", models.DecimalField(decimal_places=2, default=0, max_digits=18, verbose_name="日限额")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={
                "verbose_name": "风险等级限额",
                "verbose_name_plural": "风险等级限额",
                "db_table": "param_risk_rating_limit",
                "ordering": ["risk_level"],
            },
        ),
        migrations.RunPython(seed_risk_rating_limits, unseed_risk_rating_limits),
    ]
