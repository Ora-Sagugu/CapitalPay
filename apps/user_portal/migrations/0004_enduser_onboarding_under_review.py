from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("user_portal", "0003_useronboarding_account_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="enduser",
            name="onboarding_status",
            field=models.CharField(
                choices=[
                    ("none", "未填写"),
                    ("pending", "待审核"),
                    ("under_review", "审核中"),
                    ("approved", "已通过"),
                    ("rejected", "已拒绝"),
                ],
                default="none",
                max_length=16,
                verbose_name="资料审核状态",
            ),
        ),
    ]
