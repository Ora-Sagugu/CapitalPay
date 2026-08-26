from rest_framework import serializers
from .models import BankChannel, RoutingRule, RoutingLog, BankTransaction


class BankChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankChannel
        fields = "__all__"


class BankChannelListSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankChannel
        fields = [
            "id", "bank_code", "bank_name", "channel_type", "status",
            "priority", "success_rate", "avg_response_time", "daily_limit",
            "fee_rate", "min_fee", "max_fee", "country",
            "usd_balance", "hkd_balance", "cny_balance",
            "supported_currencies", "supported_countries", "created_at", "updated_at"
        ]


class BankChannelCreateUpdateSerializer(serializers.Serializer):
    bank_code = serializers.CharField(max_length=20)
    bank_name = serializers.CharField(max_length=100)
    channel_type = serializers.ChoiceField(choices=BankChannel.ChannelType.choices, default="online")
    status = serializers.ChoiceField(choices=BankChannel.Status.choices, default="active")
    priority = serializers.IntegerField(min_value=1, max_value=999, default=100)
    success_rate = serializers.DecimalField(max_digits=5, decimal_places=2, default=99.00)
    avg_response_time = serializers.IntegerField(default=500)
    daily_limit = serializers.DecimalField(max_digits=18, decimal_places=2, default=999999999.99)
    fee_rate = serializers.DecimalField(max_digits=5, decimal_places=4, default=0.0010)
    min_fee = serializers.DecimalField(max_digits=12, decimal_places=2, default=1.00)
    max_fee = serializers.DecimalField(max_digits=12, decimal_places=2, default=500.00)
    country = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    usd_balance = serializers.DecimalField(max_digits=18, decimal_places=2, default=0)
    hkd_balance = serializers.DecimalField(max_digits=18, decimal_places=2, default=0)
    cny_balance = serializers.DecimalField(max_digits=18, decimal_places=2, default=0)
    api_endpoint = serializers.URLField(required=False, allow_blank=True)
    health_check_url = serializers.URLField(required=False, allow_blank=True)
    supported_currencies = serializers.ListField(child=serializers.CharField(), default=list)
    supported_countries = serializers.ListField(child=serializers.CharField(), default=list)
    remark = serializers.CharField(required=False, allow_blank=True)


class BankTransactionSerializer(serializers.ModelSerializer):
    bank_name = serializers.CharField(source="bank.bank_name", read_only=True)

    class Meta:
        model = BankTransaction
        fields = [
            "id", "bank", "bank_name", "txn_date", "prn",
            "beneficiary_name", "amount", "currency", "fee", "balance", "created_at"
        ]


class RoutingRuleSerializer(serializers.ModelSerializer):
    channel_count = serializers.IntegerField(source="target_channels.count", read_only=True)
    target_channel_ids = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False, default=list
    )

    class Meta:
        model = RoutingRule
        fields = [
            "id", "name", "rule_type", "status", "priority", "weight",
            "conditions", "target_channels", "target_channel_ids",
            "fallback_channel", "channel_count", "description",
            "created_at", "updated_at"
        ]


class RoutingLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoutingLog
        fields = "__all__"
