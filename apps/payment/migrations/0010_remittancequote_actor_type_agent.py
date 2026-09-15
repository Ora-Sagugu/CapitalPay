from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payment", "0009_agent_remittance_review"),
    ]

    operations = [
        migrations.AlterField(
            model_name="remittancequote",
            name="actor_type",
            field=models.CharField(
                choices=[("ADMIN", "运营"), ("CUSTOMER", "客户"), ("AGENT", "代理")],
                max_length=16,
                verbose_name="报价发起方",
            ),
        ),
    ]
