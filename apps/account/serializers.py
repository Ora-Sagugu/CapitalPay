"""账户体系 — DRF 序列化器。"""
import datetime
import uuid
from django.utils import timezone
from rest_framework import serializers
from .models import (
    NostroAccount, UserAccount, FundTransfer, UserPaymentDetail, DepositRequest,
    VirtualAccount, VaLedgerEntry, AgentDisbursement, DisbursementApproval,
)


class NostroAccountSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.merchant_name", read_only=True, default=None)
    merchant_no = serializers.CharField(source="merchant.merchant_no", read_only=True, default=None)
    agent_name = serializers.CharField(source="agent.agent_name", read_only=True, default=None)
    agent_no = serializers.CharField(source="agent.agent_no", read_only=True, default=None)
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
            "agent", "agent_name", "agent_no",
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
        if not validated_data.get("account_number"):
            validated_data["account_number"] = validated_data["account_no"]
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

    def create(self, validated_data):
        from apps.core.utils import generate_batch_no
        validated_data["transfer_no"] = generate_batch_no("T")
        return super().create(validated_data)


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
    merchant_name = serializers.SerializerMethodField()
    agent_name = serializers.SerializerMethodField()
    agent_no = serializers.SerializerMethodField()
    account_no = serializers.CharField(source="account.account_no", read_only=True, default=None)
    account_bank_name = serializers.CharField(source="account.bank_name", read_only=True, default=None)

    class Meta:
        model = DepositRequest
        fields = [
            "id", "deposit_no", "source",
            "merchant", "merchant_name",
            "agent", "agent_name", "agent_no",
            "account", "account_no", "account_bank_name",
            "currency", "amount", "status", "remark",
            "reviewed_by", "reviewed_at", "review_comment",
            "created_at",
        ]
        read_only_fields = ["id", "deposit_no", "reviewed_by", "reviewed_at", "created_at"]

    def get_merchant_name(self, obj):
        return obj.merchant.merchant_name if obj.merchant_id else ""

    def get_agent_name(self, obj):
        return obj.agent.agent_name if obj.agent_id else ""

    def get_agent_no(self, obj):
        return obj.agent.agent_no if obj.agent_id else ""

    def validate(self, attrs):
        source = attrs.get("source") or DepositRequest.DepositSource.CUSTOMER
        attrs["source"] = source
        merchant = attrs.get("merchant")
        agent = attrs.get("agent")
        if source == DepositRequest.DepositSource.AGENT_SELF:
            if not agent:
                raise serializers.ValidationError({"agent": "Agent is required"})
            attrs["merchant"] = None
        else:
            if not merchant:
                raise serializers.ValidationError({"merchant": "Customer is required"})
            if not agent:
                attrs["agent"] = getattr(merchant, "agent", None)
        return attrs

    def create(self, validated_data):
        from apps.account.services import AccountService
        validated_data["deposit_no"] = AccountService.generate_deposit_no()
        return super().create(validated_data)


class VirtualAccountSerializer(serializers.ModelSerializer):
    """虚拟账户序列化器 — 余额由母账户派生(账实分离)。"""
    merchant_name = serializers.CharField(source="merchant.merchant_name", read_only=True, default=None)
    merchant_no = serializers.CharField(source="merchant.merchant_no", read_only=True, default=None)
    agent_name = serializers.CharField(source="agent.agent_name", read_only=True, default=None)
    agent_no = serializers.CharField(source="agent.agent_no", read_only=True, default=None)
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
            "agent", "agent_name", "agent_no",
            "order", "order_no",
            "bank_code", "bank_name", "account_holder",
            "routing_code", "clearing_network", "clearing_network_label", "country", "currency",
            "balance", "ledger_balance", "available_balance", "status",
            "opened_at", "closed_at", "close_reason",
            "created_at",
        ]
        read_only_fields = ["id", "va_number", "opened_at", "closed_at", "created_at", "ledger_balance", "available_balance"]

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


class VaLedgerEntrySerializer(serializers.ModelSerializer):
    va_number = serializers.CharField(source="virtual_account.va_number", read_only=True)
    order_no = serializers.CharField(source="order.order_no", read_only=True, default=None)

    class Meta:
        model = VaLedgerEntry
        fields = [
            "id", "va_number", "order_no", "entry_type", "amount",
            "balance_after", "source_type", "source_id", "remark", "created_at",
        ]
        read_only_fields = fields


class DisbursementApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisbursementApproval
        fields = ["id", "step", "approver", "action", "comment", "approved_at", "created_at"]
        read_only_fields = fields


class AgentDisbursementSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source="agent.agent_name", read_only=True)
    agent_no = serializers.CharField(source="agent.agent_no", read_only=True)
    approvals = DisbursementApprovalSerializer(many=True, read_only=True)

    class Meta:
        model = AgentDisbursement
        fields = [
            "id", "disbursement_no", "agent", "agent_name", "agent_no",
            "currency", "amount", "payee_bank_name", "payee_account_no",
            "payee_account_holder", "swift_code", "remark", "status",
            "approved_at", "executed_at", "fail_reason", "notify_status",
            "approvals", "created_at",
        ]
        read_only_fields = [
            "id", "disbursement_no", "status", "approved_at", "executed_at",
            "fail_reason", "created_at",
        ]

    def create(self, validated_data):
        from .services import DisbursementService
        return DisbursementService().submit(
            agent=validated_data["agent"],
            amount=validated_data["amount"],
            currency=validated_data.get("currency") or "USD",
            payee_bank_name=validated_data["payee_bank_name"],
            payee_account_no=validated_data["payee_account_no"],
            payee_account_holder=validated_data.get("payee_account_holder") or "",
            swift_code=validated_data.get("swift_code") or "",
            remark=validated_data.get("remark") or "",
        )
