"""对账 — DRF 序列化器。"""
from rest_framework import serializers
from .models import ReconciliationBatch, ReconciliationDiff, NostroBalanceCheck, ReconAlert, ReconAlertConfig


class ReconciliationBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReconciliationBatch
        fields = [
            "id", "batch_no", "bank_code", "bank_name",
            "reconciliation_date", "recon_type", "total_count_bank", "total_amount_bank",
            "total_count_platform", "total_amount_platform",
            "match_count", "match_amount", "diff_count", "diff_amount",
            "status", "started_at", "completed_at", "created_at",
        ]
        read_only_fields = fields


class ReconciliationDiffSerializer(serializers.ModelSerializer):
    batch_no = serializers.CharField(source="batch.batch_no", read_only=True)

    class Meta:
        model = ReconciliationDiff
        fields = [
            "id", "batch", "batch_no", "diff_type",
            "order_no", "prn_code", "bank_txn_id", "txn_time",
            "amount_bank", "amount_platform",
            "resolution", "resolution_note", "resolved_by", "resolved_at",
            "created_at",
        ]
        read_only_fields = ["id", "batch", "batch_no", "created_at"]


class DiffResolveSerializer(serializers.Serializer):
    """差异处理请求。"""
    resolution = serializers.ChoiceField(
        choices=["ADJUST_BANK", "ADJUST_PLATFORM", "MANUAL_CHECK", "IGNORED"]
    )
    resolved_by = serializers.CharField(max_length=64)
    note = serializers.CharField(max_length=256, required=False, allow_blank=True)


class NostroBalanceCheckSerializer(serializers.ModelSerializer):
    account_no = serializers.CharField(source="nostro_account.account_no", read_only=True)
    bank_name = serializers.CharField(source="nostro_account.bank_name", read_only=True)

    class Meta:
        model = NostroBalanceCheck
        fields = [
            "id", "check_date", "account_no", "bank_name",
            "platform_balance", "bank_statement_balance",
            "difference", "is_balanced", "remark", "created_at",
        ]
        read_only_fields = fields


class ReconAlertSerializer(serializers.ModelSerializer):
    batch_no = serializers.CharField(source="batch.batch_no", read_only=True)
    bank_name = serializers.CharField(source="batch.bank_name", read_only=True)

    class Meta:
        model = ReconAlert
        fields = [
            "id", "batch", "batch_no", "bank_name", "severity", "title", "summary",
            "channel", "status", "sent_at", "delivery_error",
            "acked_by", "acked_at", "created_at",
        ]
        read_only_fields = fields


class ReconAlertConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReconAlertConfig
        fields = ["id", "enabled", "webhook_url", "email", "updated_at"]
        read_only_fields = ["id", "updated_at"]
