# Generated manually for Remittance Fee percent_rate 2dp

from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("param", "0004_remittance_fee_config"),
    ]

    operations = [
        migrations.AlterField(
            model_name="remittancefeeconfig",
            name="percent_rate",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="例如 0.30 表示 0.30%",
                max_digits=8,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("100")),
                ],
                verbose_name="汇款百分比(%)",
            ),
        ),
    ]
