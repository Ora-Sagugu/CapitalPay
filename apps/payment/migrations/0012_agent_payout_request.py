from django.db import migrations, models


def backfill_pending_payout_requests(apps, schema_editor):
    PaymentOrder = apps.get_model("payment", "PaymentOrder")
    Merchant = apps.get_model("merchant", "Merchant")
    agent_merchant_ids = Merchant.objects.filter(agent_id__isnull=False).values_list("pk", flat=True)
    PaymentOrder.objects.filter(
        status="PAY_RECEIVED",
        merchant_id__in=agent_merchant_ids,
        is_deleted=False,
    ).update(agent_payout_request_status="pending")


class Migration(migrations.Migration):

    dependencies = [
        ("payment", "0011_order_status_default_pending_review"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentorder",
            name="agent_payout_request_status",
            field=models.CharField(
                choices=[
                    ("none", "无需代理催促"),
                    ("pending", "待代理催促打款"),
                    ("requested", "代理已催促打款"),
                ],
                db_index=True,
                default="none",
                max_length=16,
                verbose_name="代理催促打款状态",
            ),
        ),
        migrations.AddField(
            model_name="paymentorder",
            name="agent_payout_requested_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="代理催促时间"),
        ),
        migrations.AddField(
            model_name="paymentorder",
            name="agent_payout_requested_by",
            field=models.CharField(blank=True, default="", max_length=64, verbose_name="代理催促人"),
        ),
        migrations.RunPython(backfill_pending_payout_requests, migrations.RunPython.noop),
    ]
