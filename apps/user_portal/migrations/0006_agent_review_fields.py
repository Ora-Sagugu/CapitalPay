from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("user_portal", "0005_portal_role_and_agent"),
    ]

    operations = [
        migrations.AddField(
            model_name="useronboarding",
            name="agent_review_status",
            field=models.CharField(
                choices=[
                    ("none", "无需代理审核"),
                    ("pending", "待代理审核"),
                    ("approved", "代理已通过"),
                    ("rejected", "代理已拒绝"),
                ],
                default="none",
                max_length=16,
                verbose_name="代理审核状态",
            ),
        ),
        migrations.AddField(
            model_name="useronboarding",
            name="agent_reviewed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="代理审核时间"),
        ),
        migrations.AddField(
            model_name="useronboarding",
            name="agent_reviewer",
            field=models.CharField(blank=True, max_length=64, verbose_name="代理审核人"),
        ),
        migrations.AddField(
            model_name="useronboarding",
            name="agent_remark",
            field=models.CharField(blank=True, max_length=512, verbose_name="代理审核备注"),
        ),
    ]
