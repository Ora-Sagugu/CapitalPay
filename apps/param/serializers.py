from rest_framework import serializers
from .models import CoopBank, FeeModel, BankFeeConfig, RiskRatingLimit, RemittanceFeeConfig


class CoopBankSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoopBank
        fields = "__all__"


class CoopBankListSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoopBank
        fields = [
            "id", "bank_code", "bank_name", "bank_name_en", "swift_code",
            "country", "city", "status", "settlement_cycle", "daily_limit",
            "support_wire", "support_ach", "support_realtime",
            "nostro_account", "nostro_currency", "created_at"
        ]


class FeeModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeModel
        fields = "__all__"


class BankFeeConfigSerializer(serializers.ModelSerializer):
    bank_name = serializers.CharField(source="bank.bank_name", read_only=True)
    bank_code = serializers.CharField(source="bank.bank_code", read_only=True)
    fee_model_name = serializers.CharField(source="fee_model.model_name", read_only=True)

    class Meta:
        model = BankFeeConfig
        fields = [
            "id", "bank", "bank_code", "bank_name", "fee_model", "fee_model_name",
            "channel_type", "override_rate", "override_min_fee", "override_max_fee",
            "status", "effective_date", "expiry_date", "remark", "created_at", "updated_at"
        ]


class RiskRatingLimitSerializer(serializers.ModelSerializer):
    daily_limit = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True,
    )

    class Meta:
        model = RiskRatingLimit
        fields = [
            "id", "risk_level", "max_single_amount", "daily_count", "daily_limit",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "risk_level", "daily_limit", "created_at", "updated_at"]


class RemittanceFeeConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = RemittanceFeeConfig
        fields = [
            "id", "fixed_fee", "percent_rate", "max_fee",
            "updated_by", "updated_at",
        ]
        read_only_fields = ["id", "updated_by", "updated_at"]

    def validate(self, attrs):
        instance = self.instance
        fixed = attrs.get("fixed_fee", getattr(instance, "fixed_fee", 0) if instance else 0)
        max_fee = attrs.get("max_fee", getattr(instance, "max_fee", 0) if instance else 0)
        if max_fee is not None and fixed is not None and max_fee < fixed:
            raise serializers.ValidationError({
                "max_fee": "The maximum charge cannot be lower than the fixed fee",
            })
        return attrs
