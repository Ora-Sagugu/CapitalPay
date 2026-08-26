"""账户体系 — DRF 序列化器。"""
import datetime
import uuid
from django.utils import timezone
from rest_framework import serializers
from .models import NostroAccount, UserAccount, FundTransfer, UserPaymentDetail, DepositRequest, VirtualAccount


class NostroAccountSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.merchant_name", read_only=True, default=None)
    merchant_no = serializers.CharField(source="merchant.merchant_no", read_only=True, default=None)
    virtual_accounts_total = serializers.SerializerMethodField()
    virtual_accounts_count = serializers.SerializerMethodField()

    class Meta:
        model = NostroAccount
        fields = [
            "id", "account_no", "bank_code", "bank_name",
            "account_type", "currency", "balance", "virtual_accounts_total", "virtual_accounts_count",
            "last_reconciled_balance", "last_reconciled_at",
            "is_active", "account_number", "created_at",
            "merchant", "merchant_name", "merchant_no",
            "max_single_amount", "daily_limit",
            "closed_at", "close_reason",
        ]
        read_only_fields = ["id", "account_no", "created_at", "closed_at"]

    def get_virtual_accounts_total(self, obj):
        return obj.virtual_accounts_total

    def get_virtual_accounts_count(self, obj):
        return obj.virtual_accounts_count

    def create(self, validated_data):
        """创建 Nostro 账户，自动生成 account_no。"""
        validated_data["account_no"] = (
            f"N{datetime.date.today().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
        )
        return super().create(validated_data)


class UserAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAccount
        fields = [
            "id", "user_id", "bank_code", "bank_name",
            "account_holder", "status", "bind_at", "expire_at",
        ]
        read_only_fields = ["id", "created_at"]


class FundTransferSerializer(serializers.ModelSerializer):
    from_bank = serializers.CharField(source="from_account.bank_name", read_only=True)
    to_bank = serializers.CharField(source="to_account.bank_name", read_only=True)

    class Meta:
        model = FundTransfer
        fields = [
            "id", "transfer_no", "from_account", "to_account",
            "from_bank", "to_bank", "amount", "currency",
            "status", "remark", "executed_at", "created_at",
        ]
        read_only_fields = ["id", "transfer_no", "executed_at", "created_at"]


class UserPaymentDetailSerializer(serializers.ModelSerializer):
    order_no = serializers.CharField(source="order.order_no", read_only=True)

    class Meta:
        model = UserPaymentDetail
        fields = [
            "id", "user_id", "order_no", "pay_method",
            "amount", "pay_time",
        ]
        read_only_fields = fields


class DepositRequestSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.merchant_name", read_only=True)
    account_no = serializers.CharField(source="account.account_no", read_only=True, default=None)
    account_bank_name = serializers.CharField(source="account.bank_name", read_only=True, default=None)

    class Meta:
        model = DepositRequest
        fields = [
            "id", "deposit_no", "merchant", "merchant_name",
            "account", "account_no", "account_bank_name",
            "currency", "amount", "status", "remark",
            "reviewed_by", "reviewed_at", "review_comment",
            "created_at",
        ]
        read_only_fields = ["id", "deposit_no", "reviewed_by", "reviewed_at", "created_at"]

    def create(self, validated_data):
        import uuid, datetime
        validated_data["deposit_no"] = f"D{datetime.date.today().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
        return super().create(validated_data)


class VirtualAccountSerializer(serializers.ModelSerializer):
    """虚拟账户序列化器 — 余额由母账户派生(账实分离)。"""
    merchant_name = serializers.CharField(source="merchant.merchant_name", read_only=True, default=None)
    merchant_no = serializers.CharField(source="merchant.merchant_no", read_only=True, default=None)
    master_account_no = serializers.CharField(source="master_account.account_no", read_only=True, default=None)
    order_no = serializers.CharField(source="order.order_no", read_only=True, default=None)
    balance = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True, source="ledger_balance"
    )
    clearing_network_label = serializers.SerializerMethodField()

    class Meta:
        model = VirtualAccount
        fields = [
            "id", "va_number", "va_type", "label", "reference",
            "master_account", "master_account_no",
            "merchant", "merchant_name", "merchant_no",
            "order", "order_no",
            "bank_code", "bank_name", "account_holder",
            "routing_code", "clearing_network", "clearing_network_label", "country", "currency",
            "balance", "status", "opened_at", "closed_at", "close_reason",
            "created_at",
        ]
        read_only_fields = ["id", "va_number", "opened_at", "closed_at", "created_at"]

    def get_clearing_network_label(self, obj):
        return obj.get_clearing_network_display()

    def create(self, validated_data):
        """创建虚拟账户，自动生成 va_number 与开通时间。"""
        va_type = validated_data.get("va_type") or VirtualAccount.VaType.VAV
        prefix = "VLA" if va_type == VirtualAccount.VaType.VLA else "VAV"
        validated_data["va_number"] = (
            f"{prefix}{datetime.date.today().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"
        )
        validated_data["opened_at"] = timezone.now()
        return super().create(validated_data)
