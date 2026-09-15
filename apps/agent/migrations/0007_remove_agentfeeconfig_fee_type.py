from collections import defaultdict

from django.db import migrations


def dedupe_agent_fee_configs(apps, schema_editor):
    AgentFeeConfig = apps.get_model("agent", "AgentFeeConfig")
    grouped = defaultdict(list)
    for row in AgentFeeConfig.objects.all().order_by("id"):
        grouped[(row.agent_id, row.currency)].append(row)

    ids_to_delete = []
    for rows in grouped.values():
        if len(rows) == 1:
            continue
        keep = next((row for row in rows if row.fee_type == "TRANSACTION"), rows[0])
        ids_to_delete.extend(row.pk for row in rows if row.pk != keep.pk)

    if ids_to_delete:
        AgentFeeConfig.objects.filter(pk__in=ids_to_delete).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("agent", "0006_p0_core_gaps"),
    ]

    operations = [
        migrations.RunPython(dedupe_agent_fee_configs, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="agentfeeconfig",
            unique_together={("agent", "currency")},
        ),
        migrations.RemoveField(
            model_name="agentfeeconfig",
            name="fee_type",
        ),
        migrations.AlterModelOptions(
            name="agentfeeconfig",
            options={
                "ordering": ["agent", "currency"],
                "verbose_name": "代理商费率配置",
                "verbose_name_plural": "代理商费率配置",
            },
        ),
    ]
