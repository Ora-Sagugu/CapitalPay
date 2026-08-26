"""商户管理 — DRF 序列化器。"""
from rest_framework import serializers
from django.db import models
from .models import Merchant, MerchantKYC, MerchantFee, MerchantSettlementAccount, MerchantPaymentProduct


def _merchant_balance(merchant):
    """聚合该客户关联的 Nostro 账户余额。

    无关联账户时默认返回 (0, 'CNY')，满足「每个客户都能查到余额，默认为0」。
    多币种账户时按统一币种展示（取唯一币种，否则 CNY）。
    """
    accounts = merchant.nostro_accounts.filter(is_deleted=False)
    if not accounts.exists():
        return 0, "CNY"
    total = accounts.aggregate(total=models.Sum("balance"))["total"] or 0
    currencies = {a.currency for a in accounts}
    currency = currencies.pop() if len(currencies) == 1 else "CNY"
    return float(total), currency


class MerchantSerializer(serializers.ModelSerializer):
    days_to_expiry_calc = serializers.IntegerField(read_only=True)
    agent_name = serializers.CharField(source="agent.agent_name", read_only=True, default="")
    balance = serializers.SerializerMethodField()
    balance_currency = serializers.SerializerMethodField()

    class Meta:
        model = Merchant
        fields = [
            "id", "merchant_no", "merchant_name", "short_name",
            "status", "contact_name", "contact_phone", "contact_email",
            "legal_person_name", "license_expiry_date", "risk_level",
            "fee_rate", "fixed_fee", "max_single_amount", "daily_count", "daily_limit",
            "next_review_date", "sanction_status", "days_to_expiry",
            "days_to_expiry_calc",
            "agent", "agent_name",
            "balance", "balance_currency",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "merchant_no", "days_to_expiry_calc", "created_at", "updated_at"]

    def get_balance(self, obj):
        return _merchant_balance(obj)[0]

    def get_balance_currency(self, obj):
        return _merchant_balance(obj)[1]


class MerchantListSerializer(serializers.ModelSerializer):
    """商户列表 — 含 KYC、费用、结算账户概要。"""
    kyc_info = serializers.SerializerMethodField()
    fee_info = serializers.SerializerMethodField()
    settlement_account_info = serializers.SerializerMethodField()
    days_to_expiry_calc = serializers.IntegerField(read_only=True)
    agent_name = serializers.CharField(source="agent.agent_name", read_only=True, default="")
    balance = serializers.SerializerMethodField()
    balance_currency = serializers.SerializerMethodField()

    class Meta:
        model = Merchant
        fields = [
            "id", "merchant_no", "merchant_name", "short_name", "status",
            "contact_name", "legal_person_name", "risk_level", "sanction_status",
            "license_expiry_date", "days_to_expiry_calc",
            "fee_rate", "fixed_fee", "max_single_amount", "daily_count", "daily_limit",
            "next_review_date",
            "agent", "agent_name",
            "balance", "balance_currency",
            "kyc_info", "fee_info", "settlement_account_info",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "merchant_no", "days_to_expiry_calc", "created_at", "updated_at"]

    def get_balance(self, obj):
        return _merchant_balance(obj)[0]

    def get_balance_currency(self, obj):
        return _merchant_balance(obj)[1]

    def get_kyc_info(self, obj):
        try:
            kyc = obj.kyc
            return {
                "kyc_status": kyc.kyc_status,
                "legal_person": kyc.legal_person,
                "id_type": kyc.id_type,
                "id_number": kyc.id_number_plain or kyc.id_number,
                "nationality": kyc.nationality,
                "business_scope": kyc.business_scope or "",
                "registered_capital": str(kyc.registered_capital) if kyc.registered_capital else "",
                "established_date": str(kyc.established_date) if kyc.established_date else "",
                "registered_address": kyc.registered_address or "",
                "remark": kyc.remark or "",
                "reviewed_at": str(kyc.reviewed_at) if kyc.reviewed_at else "",
                "created_at": str(kyc.created_at) if kyc.created_at else "",
            }
        except MerchantKYC.DoesNotExist:
            return None

    def get_fee_info(self, obj):
        fees = obj.fees.filter(is_deleted=False)
        if not fees.exists():
            return None
        return MerchantFeeSerializer(fees, many=True).data

    def get_settlement_account_info(self, obj):
        accounts = obj.settlement_accounts.filter(is_deleted=False)
        if not accounts.exists():
            return None
        return SettlementAccountSerializer(accounts, many=True).data


class MerchantKYCSerializer(serializers.Serializer):
    legal_person = serializers.CharField(max_length=64)
    id_number = serializers.CharField(max_length=18)
    business_license = serializers.CharField(max_length=50, required=False, allow_blank=True)
    business_scope = serializers.CharField(required=False, allow_blank=True)
    registered_capital = serializers.DecimalField(max_digits=18, decimal_places=2, required=False)
    established_date = serializers.DateField(required=False)
    registered_address = serializers.CharField(max_length=256, required=False, allow_blank=True)


class MerchantFeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MerchantFee
        fields = [
            "id", "product_type", "fee_model", "fixed_fee", "fee_rate",
            "min_fee", "max_fee", "effective_from", "effective_to", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class SettlementAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = MerchantSettlementAccount
        fields = [
            "id", "bank_name", "bank_branch", "account_name",
            "account_type", "is_default", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class PaymentProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = MerchantPaymentProduct
        fields = ["id", "product_type", "is_enabled", "max_single_amount", "daily_limit"]
        read_only_fields = ["id"]
