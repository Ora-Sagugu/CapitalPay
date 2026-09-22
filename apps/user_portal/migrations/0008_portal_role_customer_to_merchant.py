from django.db import migrations, models


def forwards(apps, schema_editor):
    EndUser = apps.get_model("user_portal", "EndUser")
    EndUser.objects.filter(portal_role="customer").update(portal_role="merchant")


def backwards(apps, schema_editor):
    EndUser = apps.get_model("user_portal", "EndUser")
    EndUser.objects.filter(portal_role="merchant").update(portal_role="customer")


class Migration(migrations.Migration):

    dependencies = [
        ("user_portal", "0007_useronboarding_kyb_payload"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="enduser",
            name="portal_role",
            field=models.CharField(
                choices=[
                    ("none", "未选择"),
                    ("merchant", "商户"),
                    ("agent", "代理"),
                ],
                default="none",
                max_length=16,
                verbose_name="门户身份",
            ),
        ),
    ]
