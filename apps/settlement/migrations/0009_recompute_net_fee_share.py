from django.db import migrations


def recompute_net_fee_shares(apps, schema_editor):
    from apps.settlement.engine.calculator import SettlementCalculator

    SettlementCalculator().recompute_all_fee_shares()


class Migration(migrations.Migration):

    dependencies = [
        ("settlement", "0008_peer_merchant_agent"),
    ]

    operations = [
        migrations.RunPython(recompute_net_fee_shares, migrations.RunPython.noop),
    ]
