from rest_framework import serializers
from .models import CoopBank, FeeModel, BankFeeConfig


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
            "id", "bank", "bank_name", "bank_code", "fee_model", "fee_model_name",
            "channel_type", "override_rate", "override_min_fee", "override_max_fee",
            "status", "effective_date", "expiry_date", "remark", "created_at", "updated_at"
        ]
