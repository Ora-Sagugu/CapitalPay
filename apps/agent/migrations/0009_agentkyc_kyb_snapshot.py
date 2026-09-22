from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agent", "0008_delete_agentfeeconfig"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentkyc",
            name="kyb_snapshot",
            field=models.JSONField(blank=True, default=dict, verbose_name="入驻KYB快照"),
        ),
    ]
