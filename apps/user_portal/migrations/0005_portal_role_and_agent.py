from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("agent", "0006_p0_core_gaps"),
        ("user_portal", "0004_enduser_onboarding_under_review"),
    ]

    operations = [
        migrations.AddField(
            model_name="enduser",
            name="default_agent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bound_end_users",
                to="agent.agent",
                verbose_name="默认代理",
            ),
        ),
        migrations.AddField(
            model_name="enduser",
            name="portal_role",
            field=models.CharField(
                choices=[
                    ("none", "未选择"),
                    ("customer", "客户"),
                    ("agent", "代理"),
                ],
                default="none",
                max_length=16,
                verbose_name="门户身份",
            ),
        ),
        migrations.AddField(
            model_name="useronboarding",
            name="swift_code",
            field=models.CharField(blank=True, max_length=16, verbose_name="SWIFT代码"),
        ),
    ]
