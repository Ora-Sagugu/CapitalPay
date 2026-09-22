# Generated manually for merchant-owned customers

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("merchant", "0008_merchantkyc_kyb_snapshot"),
        ("agent", "0010_peer_merchant_agent"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentcustomer",
            name="merchant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="customers",
                to="merchant.merchant",
                verbose_name="商户",
            ),
        ),
        migrations.AlterField(
            model_name="agentcustomer",
            name="agent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="customers",
                to="agent.agent",
                verbose_name="代理商",
            ),
        ),
        migrations.AlterModelOptions(
            name="agentcustomer",
            options={
                "ordering": ["-created_at"],
                "verbose_name": "商户客户",
                "verbose_name_plural": "商户客户",
            },
        ),
    ]
