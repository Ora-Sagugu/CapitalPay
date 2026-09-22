# Each bank channel holds a single currency balance (currency + balance).

from decimal import Decimal

from django.db import migrations, models


def forwards_single_currency(apps, schema_editor):
    BankChannel = apps.get_model("routing", "BankChannel")
    preference = ("USD", "HKD", "CNY")
    field_map = {
        "USD": "usd_balance",
        "HKD": "hkd_balance",
        "CNY": "cny_balance",
    }
    for channel in BankChannel.objects.all():
        supported = list(channel.supported_currencies or [])
        chosen = None
        amount = Decimal("0")

        # Prefer an existing supported currency that has a non-zero balance.
        for code in supported:
            key = str(code or "").upper()
            field = field_map.get(key)
            if not field:
                continue
            value = Decimal(str(getattr(channel, field, 0) or 0))
            if value != 0:
                chosen = key
                amount = value
                break

        if chosen is None:
            # Otherwise pick the largest among USD/HKD/CNY (tie-break preference order).
            best = Decimal("0")
            for code in preference:
                value = Decimal(str(getattr(channel, field_map[code], 0) or 0))
                if chosen is None or value > best:
                    chosen = code
                    best = value
            amount = best
            if amount == 0 and supported:
                chosen = str(supported[0]).upper()[:3] or "USD"

        channel.currency = (chosen or "USD")[:3]
        channel.balance = amount
        channel.save(update_fields=["currency", "balance"])


def backwards_split_balances(apps, schema_editor):
    BankChannel = apps.get_model("routing", "BankChannel")
    for channel in BankChannel.objects.all():
        code = str(channel.currency or "USD").upper()
        amount = Decimal(str(channel.balance or 0))
        channel.usd_balance = amount if code == "USD" else Decimal("0")
        channel.hkd_balance = amount if code == "HKD" else Decimal("0")
        channel.cny_balance = amount if code == "CNY" else Decimal("0")
        channel.supported_currencies = [code] if code else ["USD"]
        channel.save(
            update_fields=[
                "usd_balance",
                "hkd_balance",
                "cny_balance",
                "supported_currencies",
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        ("routing", "0005_bankchannel_account_number_style"),
    ]

    operations = [
        migrations.AddField(
            model_name="bankchannel",
            name="currency",
            field=models.CharField(default="USD", max_length=3, verbose_name="币种"),
        ),
        migrations.AddField(
            model_name="bankchannel",
            name="balance",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=18, verbose_name="余额"
            ),
        ),
        migrations.RunPython(forwards_single_currency, backwards_split_balances),
        migrations.RemoveField(model_name="bankchannel", name="usd_balance"),
        migrations.RemoveField(model_name="bankchannel", name="hkd_balance"),
        migrations.RemoveField(model_name="bankchannel", name="cny_balance"),
        migrations.RemoveField(model_name="bankchannel", name="supported_currencies"),
    ]
