"""Agent serializers"""
from rest_framework import serializers
from .models import Agent, AgentMerchant, AgentCommission, AgentFeeConfig, AgentKYC


class AgentSerializer(serializers.ModelSerializer):
    merchant_count = serializers.SerializerMethodField()
    total_commission = serializers.SerializerMethodField()
    kyc_status = serializers.SerializerMethodField()

    class Meta:
        model = Agent
        fields = "__all__"
        read_only_fields = ["agent_no", "created_at", "updated_at"]

    def get_merchant_count(self, obj):
        return obj.merchant_relations.filter(is_deleted=False).count()

    def get_total_commission(self, obj):
        from django.db.models import Sum
        result = obj.commissions.filter(status__in=["SETTLED", "PAID"]).aggregate(
            total=Sum("commission_amount")
        )
        return float(result["total"] or 0)

    def get_kyc_status(self, obj):
        kyc = getattr(obj, "kyc", None)
        return kyc.kyc_status if kyc else None


class AgentListSerializer(serializers.ModelSerializer):
    """列表用 — 包含尽调核心字段"""
    merchant_count = serializers.SerializerMethodField()
    kyc_status = serializers.SerializerMethodField()

    class Meta:
        model = Agent
        fields = [
            "id", "agent_no", "agent_name", "short_name", "level", "status",
            "contact_name", "contact_phone", "contact_email",
            "commission_rate", "merchant_count", "kyc_status",
            "legal_person", "business_license_no",
            "settlement_bank_name", "settlement_account_no", "swift_code",
            "created_at",
        ]

    def get_merchant_count(self, obj):
        return obj.merchant_relations.filter(is_deleted=False).count()

    def get_kyc_status(self, obj):
        kyc = getattr(obj, "kyc", None)
        return kyc.kyc_status if kyc else None


class AgentMerchantSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source="agent.agent_name", read_only=True)
    merchant_name = serializers.CharField(source="merchant.merchant_name", read_only=True)

    class Meta:
        model = AgentMerchant
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class AgentFeeConfigSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source="agent.agent_name", read_only=True)
    agent_no = serializers.CharField(source="agent.agent_no", read_only=True)
    fee_type_display = serializers.CharField(source="get_fee_type_display", read_only=True)
    currency_display = serializers.CharField(source="get_currency_display", read_only=True)

    class Meta:
        model = AgentFeeConfig
        fields = [
            "id", "agent", "agent_name", "agent_no",
            "fee_type", "fee_type_display",
            "currency", "currency_display",
            "rate", "fixed_fee", "min_amount", "max_amount",
            "is_active", "remark",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class AgentCommissionSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source="agent.agent_name", read_only=True)
    merchant_name = serializers.CharField(source="merchant.merchant_name", read_only=True)

    class Meta:
        model = AgentCommission
        fields = "__all__"
        read_only_fields = ["commission_no", "created_at", "updated_at"]


class AgentKYCSerializer(serializers.ModelSerializer):
    agent_no = serializers.CharField(source="agent.agent_no", read_only=True)
    agent_name = serializers.CharField(source="agent.agent_name", read_only=True)

    class Meta:
        model = AgentKYC
        fields = [
            "id", "agent", "agent_no", "agent_name", "tier",
            "legal_person", "id_type", "id_number", "id_number_plain",
            "business_license", "business_scope", "registered_capital",
            "established_date", "registered_address", "kyc_status",
            "submitted_at", "reviewed_by", "reviewed_at", "review_comment",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "kyc_status", "submitted_at", "reviewed_by", "reviewed_at",
            "review_comment", "created_at", "updated_at",
        ]

    def create(self, validated_data):
        plain = validated_data.get("id_number_plain") or ""
        if plain and not validated_data.get("id_number"):
            validated_data["id_number"] = plain
        if not validated_data.get("business_license"):
            validated_data["business_license"] = plain or "N/A"
        return super().create(validated_data)
