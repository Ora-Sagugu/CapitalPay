from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agent", "0007_remove_agentfeeconfig_fee_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="agent",
            name="commission_rate",
            field=models.DecimalField(
                decimal_places=6,
                default=0,
                help_text="该代理名下客户交易手续费的分成比例，0.50 表示 50%",
                max_digits=8,
                verbose_name="佣金比例",
            ),
        ),
        migrations.DeleteModel(
            name="AgentFeeConfig",
        ),
    ]
