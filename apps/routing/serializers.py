from rest_framework import serializers
from decimal import Decimal
from .models import BankChannel, RoutingRule, RoutingLog, BankTransaction


class BankChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankChannel
        fields = "__all__"


class BankChannelListSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankChannel
        fields = [
            "id", "bank_code", "bank_name", "account_number", "channel_type", "status",
            "priority", "success_rate", "avg_response_time", "daily_limit",
            "fee_rate", "max_fee", "country",
            "currency", "balance",
            "supported_countries", "created_at", "updated_at"
        ]


class BankChannelCreateUpdateSerializer(serializers.Serializer):
    bank_code = serializers.CharField(max_length=20)
    bank_name = serializers.CharField(max_length=100)
    account_number = serializers.CharField(max_length=64)
    channel_type = serializers.ChoiceField(choices=BankChannel.ChannelType.choices, default="online")
    status = serializers.ChoiceField(choices=BankChannel.Status.choices, default="active")
    priority = serializers.IntegerField(min_value=1, max_value=999, default=100)
    success_rate = serializers.DecimalField(max_digits=5, decimal_places=2, default=99.00)
    avg_response_time = serializers.IntegerField(default=500)
    daily_limit = serializers.DecimalField(max_digits=18, decimal_places=2, default=999999999.99)
    fee_rate = serializers.DecimalField(max_digits=5, decimal_places=4, default=0.0010)
    max_fee = serializers.DecimalField(max_digits=12, decimal_places=2, default=500.00)
    country = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    currency = serializers.CharField(max_length=3, default="USD")
    balance = serializers.DecimalField(max_digits=18, decimal_places=2, default=0)
    api_endpoint = serializers.URLField(required=False, allow_blank=True)
    health_check_url = serializers.URLField(required=False, allow_blank=True)
    supported_countries = serializers.ListField(child=serializers.CharField(), default=list)
    remark = serializers.CharField(required=False, allow_blank=True)

    def validate_account_number(self, value):
        import re

        value = re.sub(r"\s+", "", (value or "").strip())
        if not value:
            raise serializers.ValidationError("Account number is required")
        if not re.fullmatch(r"[0-9A-Za-z]{6,34}", value):
            raise serializers.ValidationError(
                "Enter a bank account number of 6–34 digits "
                "(letters allowed for international accounts such as IBAN)"
            )
        if not any(ch.isdigit() for ch in value):
            raise serializers.ValidationError("Account number must include at least one digit")
        return value.upper() if any(ch.isalpha() for ch in value) else value

    def validate_currency(self, value):
        code = (value or "").strip().upper()
        if not code or len(code) != 3 or not code.isalpha():
            raise serializers.ValidationError("Currency must be a 3-letter ISO code")
        return code

    def validate(self, attrs):
        account_number = attrs.get("account_number")
        channel_id = self.context.get("channel_id")
        qs = BankChannel.objects.filter(account_number=account_number)
        if channel_id:
            qs = qs.exclude(pk=channel_id)
        if qs.exists():
            raise serializers.ValidationError({
                "account_number": "This bank account number is already assigned to another channel"
            })
        # Channel fees are percentage + optional max only; never apply a minimum.
        attrs["min_fee"] = Decimal("0.00")
        return attrs


class BankTransactionSerializer(serializers.ModelSerializer):
    bank_name = serializers.CharField(source="bank.bank_name", read_only=True)
    bank_code = serializers.CharField(source="bank.bank_code", read_only=True)

    class Meta:
        model = BankTransaction
        fields = [
            "id", "bank", "bank_code", "bank_name", "txn_date", "prn",
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
