from django.db import migrations, models
from django.db.models import Count


def detach_duplicate_fee_shares(apps, schema_editor):
    FeeShare = apps.get_model("settlement", "FeeShare")
    duplicates = (
        FeeShare.objects.exclude(payment_order_id=None)
        .values("payment_order_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )
    for row in duplicates.iterator():
        shares = FeeShare.objects.filter(
            payment_order_id=row["payment_order_id"]
        ).order_by("created_at")
        keep = shares.first()
        shares.exclude(pk=keep.pk).update(payment_order_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ("settlement", "0003_feeshare_payment_order_and_more"),
    ]

    operations = [
        migrations.RunPython(detach_duplicate_fee_shares, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="feeshare",
            constraint=models.UniqueConstraint(
                condition=models.Q(("payment_order__isnull", False)),
                fields=("payment_order",),
                name="unique_fee_share_payment_order",
            ),
        ),
    ]
