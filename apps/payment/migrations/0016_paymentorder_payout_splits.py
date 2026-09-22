from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payment", "0015_remittance_funding_methods"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentorder",
            name="payout_splits",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Confirm transfer 时可按剩余余额拆到最多两家银行，例如 [{bank_code, amount, computed_fee}, ...]",
                verbose_name="出款银行拆分",
            ),
        ),
    ]
