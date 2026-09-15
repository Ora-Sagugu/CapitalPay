from django.db import migrations, models

LEGACY_TO_NEW = {
    "PERSON": "INDIVIDUAL",
    "COMPANY": "ORGANIZATION",
    "CITY": "REGION",
    "COUNTRY": "COUNTRY",
    "VESSEL": "ENTITY",
    "OTHER": "ENTITY",
}


def migrate_entity_types(apps, schema_editor):
    SanctionList = apps.get_model("compliance", "SanctionList")
    for old, new in LEGACY_TO_NEW.items():
        SanctionList.objects.filter(entity_type=old).update(entity_type=new)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("compliance", "0005_ofac_un_only"),
    ]

    operations = [
        migrations.RunPython(migrate_entity_types, noop),
        migrations.AlterField(
            model_name="sanctionlist",
            name="entity_type",
            field=models.CharField(
                choices=[
                    ("INDIVIDUAL", "Individual"),
                    ("ENTITY", "Entity"),
                    ("ORGANIZATION", "Organization"),
                    ("COUNTRY", "Country"),
                    ("REGION", "Region"),
                ],
                default="INDIVIDUAL",
                max_length=32,
                verbose_name="实体类型",
            ),
        ),
    ]
