from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("user_portal", "0002_alter_useronboarding_id_back_image_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="useronboarding",
            name="account_name",
            field=models.CharField(blank=True, max_length=256, verbose_name="账户名"),
        ),
    ]
