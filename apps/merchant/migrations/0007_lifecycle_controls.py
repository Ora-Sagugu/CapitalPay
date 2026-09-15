import uuid

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def reconcile_merchant_states(apps, schema_editor):
    Merchant = apps.get_model("merchant", "Merchant")
    MerchantKYC = apps.get_model("merchant", "MerchantKYC")
    MerchantFee = apps.get_model("merchant", "MerchantFee")
    MerchantPaymentProduct = apps.get_model("merchant", "MerchantPaymentProduct")
    MerchantSettlementAccount = apps.get_model("merchant", "MerchantSettlementAccount")
    MerchantStatusEvent = apps.get_model("merchant", "MerchantStatusEvent")
    today = django.utils.timezone.localdate()

    for merchant in Merchant.objects.filter(is_deleted=False).iterator():
        original_status = merchant.status
        reason = {
            "PENDING": "KYC_PENDING",
            "ACTIVE": "LEGACY_ACTIVE",
            "SUSPENDED": "LEGACY_SUSPENDED",
            "CLOSED": "LEGACY_CLOSED",
        }.get(original_status, "LEGACY_STATE")

        if original_status == "ACTIVE":
            kyc_ok = MerchantKYC.objects.filter(
                merchant_id=merchant.id,
                kyc_status="APPROVED",
                is_deleted=False,
            ).exists()
            license_ok = bool(
                merchant.license_expiry_date
                and merchant.license_expiry_date >= today
            )
            product_ok = MerchantPaymentProduct.objects.filter(
                merchant_id=merchant.id,
                product_type="WIRE_TRANSFER",
                is_enabled=True,
                is_deleted=False,
            ).exists()
            fee_ok = MerchantFee.objects.filter(
                merchant_id=merchant.id,
                product_type="WIRE_TRANSFER",
                effective_from__lte=today,
                is_deleted=False,
            ).filter(
                models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=today)
            ).exists()
            settlement_ok = MerchantSettlementAccount.objects.filter(
                merchant_id=merchant.id,
                is_default=True,
                is_deleted=False,
            ).exists()
            if not all((kyc_ok, license_ok, product_ok, fee_ok, settlement_ok)):
                merchant.status = "SUSPENDED"
                reason = "DATA_INCONSISTENT"

        if (
            merchant.status == "SUSPENDED"
            and merchant.license_expiry_date
            and merchant.license_expiry_date < today
        ):
            reason = "LICENSE_EXPIRED"

        merchant.status_reason_code = reason
        merchant.status_changed_at = merchant.updated_at or django.utils.timezone.now()
        merchant.save(update_fields=[
            "status", "status_reason_code", "status_changed_at",
        ])
        MerchantStatusEvent.objects.create(
            id=uuid.uuid4(),
            merchant_id=merchant.id,
            from_status=original_status if original_status != merchant.status else "",
            to_status=merchant.status,
            reason_code=reason,
            comment="生命周期控制迁移生成",
            actor="migration",
            source="DATA_MIGRATION",
            is_deleted=False,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("merchant", "0006_feature_gap_split_and_recon_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="merchant",
            name="status_changed_at",
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                verbose_name="状态变更时间",
            ),
        ),
        migrations.AddField(
            model_name="merchant",
            name="status_reason_code",
            field=models.CharField(
                blank=True,
                default="",
                max_length=64,
                verbose_name="状态原因码",
            ),
        ),
        migrations.AlterField(
            model_name="merchant",
            name="status",
            field=models.CharField(
                choices=[
                    ("ACTIVE", "正常"),
                    ("SUSPENDED", "暂停"),
                    ("CLOSED", "已关闭"),
                    ("PENDING", "待处理"),
                ],
                default="PENDING",
                max_length=16,
                verbose_name="状态",
            ),
        ),
        migrations.AlterField(
            model_name="merchantkyc",
            name="kyc_status",
            field=models.CharField(
                choices=[
                    ("PENDING", "待审核"),
                    ("APPROVED", "已通过"),
                    ("REJECTED", "已驳回"),
                    ("WARNING", "需关注"),
                ],
                default="PENDING",
                max_length=16,
                verbose_name="KYC状态",
            ),
        ),
        migrations.CreateModel(
            name="MerchantStatusEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        db_index=True,
                        verbose_name="创建时间",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="更新时间"),
                ),
                (
                    "is_deleted",
                    models.BooleanField(default=False, verbose_name="软删除"),
                ),
                (
                    "from_status",
                    models.CharField(blank=True, max_length=16, verbose_name="原状态"),
                ),
                (
                    "to_status",
                    models.CharField(
                        choices=[
                            ("ACTIVE", "正常"),
                            ("SUSPENDED", "暂停"),
                            ("CLOSED", "已关闭"),
                            ("PENDING", "待处理"),
                        ],
                        max_length=16,
                        verbose_name="新状态",
                    ),
                ),
                (
                    "reason_code",
                    models.CharField(max_length=64, verbose_name="原因码"),
                ),
                (
                    "comment",
                    models.CharField(blank=True, max_length=512, verbose_name="说明"),
                ),
                (
                    "actor",
                    models.CharField(blank=True, max_length=64, verbose_name="操作人"),
                ),
                (
                    "source",
                    models.CharField(default="API", max_length=64, verbose_name="来源"),
                ),
                (
                    "merchant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="status_events",
                        to="merchant.merchant",
                        verbose_name="商户",
                    ),
                ),
            ],
            options={
                "verbose_name": "商户状态事件",
                "verbose_name_plural": "商户状态事件",
                "db_table": "merchant_status_event",
                "ordering": ["-created_at"],
            },
        ),
        migrations.RunPython(reconcile_merchant_states, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="merchant",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("status__in", ["PENDING", "ACTIVE", "SUSPENDED", "CLOSED"])
                ),
                name="merchant_valid_status",
            ),
        ),
        migrations.AddConstraint(
            model_name="merchantkyc",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("kyc_status__in", ["PENDING", "APPROVED", "REJECTED", "WARNING"])
                ),
                name="merchant_kyc_valid_status",
            ),
        ),
        migrations.AddConstraint(
            model_name="merchantstatusevent",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("to_status__in", ["PENDING", "ACTIVE", "SUSPENDED", "CLOSED"])
                ),
                name="merchant_event_valid_to_status",
            ),
        ),
        migrations.AddIndex(
            model_name="merchantstatusevent",
            index=models.Index(
                fields=["merchant", "created_at"],
                name="merchant_st_merchan_040315_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="merchantstatusevent",
            index=models.Index(
                fields=["reason_code", "created_at"],
                name="merchant_st_reason__18e00d_idx",
            ),
        ),
    ]
