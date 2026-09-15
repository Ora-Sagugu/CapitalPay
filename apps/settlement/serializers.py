"""清结算 — DRF 序列化器。"""
from rest_framework import serializers
from .models import SettlementBatch, SettlementDetail, FeeShare, DifferenceWriteOff


class SettlementBatchSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.merchant_name", read_only=True)

    class Meta:
        model = SettlementBatch
        fields = [
            "id", "batch_no", "settle_date", "merchant", "merchant_name",
            "total_count", "total_amount", "fee_total", "settle_net_amount",
            "status", "settled_at", "fail_reason", "settlement_account_info",
            "created_at", "currency", "bank_txn_id",
        ]
        read_only_fields = fields


class SettlementDetailSerializer(serializers.ModelSerializer):
    batch_no = serializers.CharField(source="batch.batch_no", read_only=True)
    merchant_name = serializers.CharField(source="batch.merchant.merchant_name", read_only=True)
    has_fee_share = serializers.SerializerMethodField()

    class Meta:
        model = SettlementDetail
        fields = [
            "id", "batch", "batch_no", "merchant_name", "order_no",
            "amount", "fee", "settle_amount", "has_fee_share", "created_at",
        ]
        read_only_fields = fields

    def get_has_fee_share(self, obj):
        return hasattr(obj, "feeshare")


class FeeShareSerializer(serializers.ModelSerializer):
    settle_date = serializers.SerializerMethodField()
    payment_order_no = serializers.CharField(source="order_no", read_only=True)
    beneficiary_name = serializers.SerializerMethodField()
    beneficiary_bank = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    total_fee = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    channel_fee = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    platform_fee = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    agent_fee = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = FeeShare
        fields = [
            "id",
            "payment_order_no",
            "order_no",
            "settle_date",
            "merchant_name",
            "agent_name",
            "bank_channel_name",
            "currency",
            "amount",
            "total_fee",
            "channel_fee",
            "platform_fee",
            "agent_fee",
            "beneficiary_name",
            "beneficiary_bank",
            "agent",
            "created_at",
        ]
        read_only_fields = fields

    def get_settle_date(self, obj):
        """从关联的汇款订单取结算时间。"""
        try:
            po = obj.payment_order
            if po and po.settled_at:
                return po.settled_at.strftime("%Y-%m-%d")
            if po and po.created_at:
                return po.created_at.strftime("%Y-%m-%d")
        except Exception:
            pass
        return None

    def get_beneficiary_name(self, obj):
        try:
            return obj.payment_order.beneficiary_name or ""
        except Exception:
            return ""

    def get_beneficiary_bank(self, obj):
        try:
            return obj.payment_order.beneficiary_bank or ""
        except Exception:
            return ""

    def get_currency(self, obj):
        try:
            return obj.payment_order.currency or "CNY"
        except Exception:
            return "CNY"


class DifferenceWriteOffSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.merchant_name", read_only=True)
    merchant_no = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = DifferenceWriteOff
        fields = [
            "id", "write_off_no", "merchant", "merchant_name", "merchant_no", "amount", "reason",
            "status", "applied_by", "approved_by", "approved_at", "created_at",
        ]
        read_only_fields = ["id", "write_off_no", "created_at"]
        extra_kwargs = {"merchant": {"required": False}}

    def validate(self, attrs):
        merchant_no = attrs.pop("merchant_no", None)
        if not attrs.get("merchant") and merchant_no:
            from apps.merchant.models import Merchant
            merchant = Merchant.objects.filter(merchant_no=merchant_no, is_deleted=False).first()
            if not merchant:
                raise serializers.ValidationError({"merchant_no": "The customer does not exist"})
            attrs["merchant"] = merchant
        if not attrs.get("merchant"):
            raise serializers.ValidationError({"merchant": "A customer number or primary key is required"})
        return attrs
