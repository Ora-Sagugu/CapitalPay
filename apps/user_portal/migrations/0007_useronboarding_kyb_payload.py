from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("user_portal", "0006_agent_review_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="useronboarding",
            name="application_ref",
            field=models.CharField(blank=True, max_length=64, verbose_name="申请编号"),
        ),
        migrations.AddField(
            model_name="useronboarding",
            name="kyb_payload",
            field=models.JSONField(blank=True, default=dict, verbose_name="KYB完整资料"),
        ),
    ]
