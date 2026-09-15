from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payment", "0008_paymentorder_applied_fee_model_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentorder",
            name="agent_review_comment",
            field=models.CharField(blank=True, default="", max_length=512, verbose_name="代理审核意见"),
        ),
        migrations.AddField(
            model_name="paymentorder",
            name="agent_review_status",
            field=models.CharField(
                choices=[
                    ("none", "无需代理审核"),
                    ("pending", "待代理审核"),
                    ("approved", "代理已同意"),
                    ("rejected", "代理已驳回"),
                ],
                db_index=True,
                default="none",
                max_length=16,
                verbose_name="代理审核状态",
            ),
        ),
        migrations.AddField(
            model_name="paymentorder",
            name="agent_reviewed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="代理审核时间"),
        ),
        migrations.AddField(
            model_name="paymentorder",
            name="agent_reviewed_by",
            field=models.CharField(blank=True, default="", max_length=64, verbose_name="代理审核人"),
        ),
        migrations.AlterField(
            model_name="paymentorder",
            name="status",
            field=models.CharField(
                choices=[
                    ("PRE_CREATE", "预创建"),
                    ("PENDING_AGENT_REVIEW", "待代理审核"),
                    ("PENDING_REVIEW", "待审核"),
                    ("PROCESSING", "处理中"),
                    ("COMPLETED", "已完成"),
                    ("PENDING_PAY", "待收款"),
                    ("PAY_RECEIVED", "已收款"),
                    ("PENDING_SETTLE", "待清算"),
                    ("SETTLED", "已清算"),
                    ("CLOSED", "已关闭"),
                    ("REFUNDING", "退款中"),
                    ("REFUNDED", "已退款"),
                ],
                default="PRE_CREATE",
                max_length=20,
                verbose_name="状态",
            ),
        ),
    ]
