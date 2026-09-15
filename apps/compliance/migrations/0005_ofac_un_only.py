from django.db import migrations, models


REMOVED_LIST_TYPES = ("EU", "MPS", "PBOC", "INTERNAL")
LEGACY_MERCHANT_STATUSES = ("EU", "HMT")


def remove_non_ofac_un_sanctions(apps, schema_editor):
    SanctionHitDetail = apps.get_model("compliance", "SanctionHitDetail")
    SanctionList = apps.get_model("compliance", "SanctionList")
    Merchant = apps.get_model("merchant", "Merchant")

    hit_deleted, _ = SanctionHitDetail.objects.filter(
        sanction_entry__list_type__in=REMOVED_LIST_TYPES
    ).delete()
    list_deleted, _ = SanctionList.objects.filter(
        list_type__in=REMOVED_LIST_TYPES
    ).delete()

    Merchant.objects.filter(sanction_status__in=LEGACY_MERCHANT_STATUSES).update(
        sanction_status="OFAC"
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("compliance", "0004_entity_type_city_country"),
        ("merchant", "0007_lifecycle_controls"),
    ]

    operations = [
        migrations.RunPython(remove_non_ofac_un_sanctions, noop),
        migrations.AlterField(
            model_name="sanctionlist",
            name="list_type",
            field=models.CharField(
                choices=[("OFAC", "OFAC(美国)"), ("UN", "联合国")],
                max_length=16,
                verbose_name="名单来源",
            ),
        ),
    ]
