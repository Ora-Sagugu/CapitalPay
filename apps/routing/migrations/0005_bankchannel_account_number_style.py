# Rewrite placeholder BA-* account numbers into bank-style digit / IBAN values.

from django.db import migrations, models

SEED_ACCOUNT_NUMBERS = {
    "ICBC": "0180100123456",
    "ABC": "0550010023456",
    "CCB": "6217000012345678",
    "BOC": "4563510000123456",
    "JPM": "0001122334",
    "HSBC": "070012345678",
    "BAC": "435601234567",
    "BNP": "FR7630004000031234567890143",
    "CRAG": "FR7611808009101234567890144",
    "PSBC": "6217990012345678",
}


def rewrite_placeholder_accounts(apps, schema_editor):
    BankChannel = apps.get_model("routing", "BankChannel")
    used = {
        (row.account_number or "").strip()
        for row in BankChannel.objects.all()
        if row.account_number and not str(row.account_number).upper().startswith("BA-")
    }
    for channel in BankChannel.objects.all().order_by("created_at"):
        current = (channel.account_number or "").strip()
        if current and not current.upper().startswith("BA-"):
            continue
        candidate = SEED_ACCOUNT_NUMBERS.get(channel.bank_code)
        if not candidate:
            digits = "".join(str(ord(ch) % 10) for ch in (channel.bank_code or "BANK"))
            candidate = f"62{digits.ljust(14, '0')[:14]}"
        base = candidate
        seq = 1
        while candidate in used:
            seq += 1
            if base[:2].isalpha():
                candidate = f"{base}{seq}"
            else:
                candidate = f"{base}{seq:02d}"[-34:]
        channel.account_number = candidate
        channel.save(update_fields=["account_number"])
        used.add(candidate)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("routing", "0004_bankchannel_account_number"),
    ]

    operations = [
        migrations.RunPython(rewrite_placeholder_accounts, noop_reverse),
        migrations.AlterField(
            model_name="bankchannel",
            name="account_number",
            field=models.CharField(
                help_text="银行账户号码：通常为纯数字；国际账号（如 IBAN）可含字母",
                max_length=64,
                unique=True,
                verbose_name="银行账号",
            ),
        ),
    ]
