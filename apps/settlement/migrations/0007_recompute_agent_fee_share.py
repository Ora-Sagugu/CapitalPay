from django.db import migrations


def recompute_agent_fee_shares(apps, schema_editor):
    from apps.settlement.engine.calculator import SettlementCalculator

    SettlementCalculator().recompute_all_fee_shares()


class Migration(migrations.Migration):

    dependencies = [
        ("settlement", "0006_payment_analytics_money_movement"),
    ]

    operations = [
        migrations.RunPython(recompute_agent_fee_shares, migrations.RunPython.noop),
    ]
