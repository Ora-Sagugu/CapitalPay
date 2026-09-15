from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("agent", "0008_delete_agentfeeconfig"),
        ("account", "0010_payment_analytics_money_movement"),
    ]

    operations = [
        migrations.AddField(
            model_name="depositrequest",
            name="agent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="deposits",
                to="agent.agent",
                verbose_name="代理商",
            ),
        ),
        migrations.AddField(
            model_name="depositrequest",
            name="source",
            field=models.CharField(
                choices=[("CUSTOMER", "客户充值"), ("AGENT_SELF", "代理自充")],
                default="CUSTOMER",
                max_length=16,
                verbose_name="来源",
            ),
        ),
        migrations.AlterField(
            model_name="depositrequest",
            name="merchant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="deposits",
                to="merchant.merchant",
                verbose_name="客户",
            ),
        ),
        migrations.AddIndex(
            model_name="depositrequest",
            index=models.Index(fields=["agent", "status"], name="deposit_req_agent_id_status_idx"),
        ),
    ]
