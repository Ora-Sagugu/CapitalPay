from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("merchant", "0007_lifecycle_controls"),
    ]

    operations = [
        migrations.AddField(
            model_name="merchantkyc",
            name="kyb_snapshot",
            field=models.JSONField(blank=True, default=dict, verbose_name="入驻KYB快照"),
        ),
    ]
