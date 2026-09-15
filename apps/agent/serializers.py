"""Agent serializers"""
from decimal import Decimal

from rest_framework import serializers
from .models import Agent, AgentMerchant, AgentCommission, AgentKYC


class AgentSerializer(serializers.ModelSerializer):
    merchant_count = serializers.SerializerMethodField()
    total_commission = serializers.SerializerMethodField()
    kyc_status = serializers.SerializerMethodField()
    accounts = serializers.SerializerMethodField()

    class Meta:
        model = Agent
        fields = "__all__"
        read_only_fields = ["level", "api_key", "api_secret", "created_at", "updated_at"]

    def validate_agent_no(self, value):
        code = (value or "").strip()
        if not code:
            raise serializers.ValidationError("Agent Code is required.")
        if len(code) > 32:
            raise serializers.ValidationError("Agent Code must be at most 32 characters.")
        qs = Agent.objects.filter(agent_no__iexact=code)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This Agent Code is already in use.")
        return code

    def validate_commission_rate(self, value):
        rate = Decimal(str(value or 0))
        if rate < 0 or rate > 1:
            raise serializers.ValidationError("Share must be between 0% and 100%.")
        return rate

    def update(self, instance, validated_data):
        old_code = (instance.agent_no or "").strip()
        new_code = validated_data.get("agent_no", old_code)
        agent = super().update(instance, validated_data)
        if old_code and new_code and old_code != new_code:
            from apps.user_portal.models import UserOnboarding

            UserOnboarding.objects.filter(agent_code__iexact=old_code).update(agent_code=new_code)
        return agent

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

    def get_accounts(self, obj):
        return [
            {
                "id": str(a.id),
                "account_no": a.account_no,
                "account_type": a.account_type,
                "currency": a.currency,
                "balance": str(a.balance),
            }
            for a in obj.nostro_accounts.filter(is_deleted=False)
        ]


class AgentListSerializer(serializers.ModelSerializer):
    """列表用 — 包含尽调核心字段"""
    merchant_count = serializers.SerializerMethodField()
    kyc_status = serializers.SerializerMethodField()
    customer_count = serializers.IntegerField(read_only=True, default=0)
    order_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Agent
        fields = [
            "id", "agent_no", "agent_name", "short_name", "status",
            "contact_name", "contact_phone", "contact_email",
            "commission_rate", "merchant_count", "customer_count", "order_count",
            "kyc_status",
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
