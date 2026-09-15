from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payment", "0010_remittancequote_actor_type_agent"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentorder",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING_AGENT_REVIEW", "待代理审核"),
                    ("PENDING_REVIEW", "待运营审核"),
                    ("PENDING_PAY", "待入金"),
                    ("PAY_RECEIVED", "已入金"),
                    ("PENDING_SETTLE", "付款处理中"),
                    ("SETTLED", "已完成"),
                    ("CLOSED", "已关闭"),
                    ("REFUNDING", "退款中"),
                    ("REFUNDED", "已退款"),
                    ("PRE_CREATE", "待入金"),
                    ("PROCESSING", "待入金"),
                    ("COMPLETED", "已完成"),
                ],
                default="PENDING_REVIEW",
                max_length=20,
                verbose_name="状态",
            ),
        ),
    ]
