from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("settlement", "0004_unique_fee_share_per_order"),
    ]

    operations = [
        migrations.AlterField(
            model_name="feeshare",
            name="total_fee",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=12, verbose_name="商户手续费总额"
            ),
        ),
        migrations.AlterField(
            model_name="feeshare",
            name="channel_fee",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=12, verbose_name="渠道手续费"
            ),
        ),
        migrations.AlterField(
            model_name="feeshare",
            name="platform_fee",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=12, verbose_name="平台净收益"
            ),
        ),
        migrations.AlterField(
            model_name="feeshare",
            name="agent_fee",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=12, verbose_name="代理商佣金"
            ),
        ),
    ]
