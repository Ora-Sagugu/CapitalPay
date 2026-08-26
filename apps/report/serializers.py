"""财务报表 — DRF 序列化器。"""
from rest_framework import serializers
from .models import MerchantDailyReport, ChannelFeeReport, PlatformOrderSummary
from apps.settlement.models import SettlementBatch, SettlementDetail


class MerchantDailyReportSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.merchant_name", read_only=True)

    class Meta:
        model = MerchantDailyReport
        fields = [
            "id", "report_date", "merchant", "merchant_name",
            "total_orders", "total_amount", "total_fee",
            "total_refunds", "total_refund_amount", "net_amount",
        ]
        read_only_fields = fields


class ChannelFeeReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChannelFeeReport
        fields = [
            "id", "report_date", "bank_code", "bank_name",
            "total_orders", "total_amount", "channel_fee", "platform_fee",
        ]
        read_only_fields = fields


class PlatformOrderSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformOrderSummary
        fields = [
            "id", "report_date", "total_merchants", "total_orders",
            "total_amount", "total_fee", "total_refunds",
            "total_refund_amount", "settled_amount",
        ]
        read_only_fields = fields


# ── 商户结算报表（基于 Settlement 模型实时查询） ──

class MerchantSettlementReportSerializer(serializers.Serializer):
    """商户结算明细表 — 实时聚合查询。"""
    merchant_no = serializers.CharField()
    merchant_name = serializers.CharField()
    batch_no = serializers.CharField()
    settle_date = serializers.DateField()
    total_count = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    fee_total = serializers.DecimalField(max_digits=18, decimal_places=2)
    settle_net_amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    status = serializers.CharField()
    settled_at = serializers.DateTimeField()


class SettlementBatchReportSerializer(serializers.ModelSerializer):
    """商户结算批次表。"""
    merchant_name = serializers.CharField(source="merchant.merchant_name", read_only=True)
    merchant_no = serializers.CharField(source="merchant.merchant_no", read_only=True)

    class Meta:
        model = SettlementBatch
        fields = [
            "batch_no", "merchant_no", "merchant_name", "settle_date",
            "total_count", "total_amount", "fee_total", "settle_net_amount",
            "status", "settled_at", "created_at",
        ]
