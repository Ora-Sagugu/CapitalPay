# Generated manually for BankChannel.account_number

from django.db import migrations, models


def backfill_account_numbers(apps, schema_editor):
    BankChannel = apps.get_model("routing", "BankChannel")
    used = set()
    for channel in BankChannel.objects.all().order_by("created_at"):
        base = f"BA-{channel.bank_code}".upper()
        candidate = base
        seq = 1
        while candidate in used or BankChannel.objects.filter(account_number=candidate).exclude(pk=channel.pk).exists():
            seq += 1
            candidate = f"{base}-{seq}"
        channel.account_number = candidate
        channel.save(update_fields=["account_number"])
        used.add(candidate)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("routing", "0003_alter_bankchannel_country"),
    ]

    operations = [
        migrations.AddField(
            model_name="bankchannel",
            name="account_number",
            field=models.CharField(
                blank=True,
                default="",
                help_text="该银行通道在本系统中的唯一账号标识，类似证件号",
                max_length=64,
                verbose_name="银行账号",
            ),
        ),
        migrations.RunPython(backfill_account_numbers, noop_reverse),
        migrations.AlterField(
            model_name="bankchannel",
            name="account_number",
            field=models.CharField(
                help_text="该银行通道在本系统中的唯一账号标识，类似证件号",
                max_length=64,
                unique=True,
                verbose_name="银行账号",
            ),
        ),
    ]
