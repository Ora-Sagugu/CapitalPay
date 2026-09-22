"""支付交易 — DRF 序列化器。"""
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from rest_framework import serializers

from .models import BankCreditNotification, PaymentOrder, RefundOrder

MONEY = Decimal("0.01")


def _quantize_money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def _empty_fee_breakdown():
    return {
        "bank_fee": None,
        "remittance_profit": None,
        "agent_fee": None,
        "capitalpay_profit": None,
    }


def resolve_order_fee_breakdown(order):
    """Resolve fee stack for order detail display.

    Remittance Fee − Bank Fee = Remittance Profit
    Remittance Profit splits by Agent Edit share into Agent Fee + CapitalPay Profit.
    """
    remittance_fee = _quantize_money(order.fee_amount)
    share = next(
        (item for item in order.fee_shares.all() if not item.is_deleted),
        None,
    )

    if not getattr(settings, "ENABLE_BANKING", True):
        if share is not None:
            bank_fee = _quantize_money(share.channel_fee)
            return {
                "bank_fee": bank_fee,
                "remittance_profit": _quantize_money(remittance_fee - bank_fee),
                "agent_fee": _quantize_money(share.agent_fee),
                "capitalpay_profit": _quantize_money(share.platform_fee),
            }
        return {
            "bank_fee": Decimal("0.00"),
            "remittance_profit": remittance_fee,
            "agent_fee": None,
            "capitalpay_profit": None,
        }

    bank_fee = None
    splits = [leg for leg in (getattr(order, "payout_splits", None) or []) if leg]
    if share is not None and (share.channel_fee or order.bank_code or splits):
        bank_fee = _quantize_money(share.channel_fee)
    elif len(splits) >= 2:
        from apps.routing.services import RoutingService

        payout_amount = RoutingService.payout_amount_for_order(order)
        bank_fee = _quantize_money(
            RoutingService.channel_fee_for_order(order, payout_amount),
        )
    elif order.bank_code:
        from apps.routing.services import RoutingService
        from apps.settlement.engine.calculator import SettlementCalculator

        channel = SettlementCalculator._lookup_bank_channel(order)
        if channel is not None:
            payout_amount = RoutingService.payout_amount_for_order(order)
            bank_fee = _quantize_money(
                RoutingService._channel_fee(channel, payout_amount),
            )

    if bank_fee is None:
        return _empty_fee_breakdown()

    remittance_profit = _quantize_money(remittance_fee - bank_fee)
    if share is not None:
        return {
            "bank_fee": bank_fee,
            "remittance_profit": remittance_profit,
            "agent_fee": _quantize_money(share.agent_fee),
            "capitalpay_profit": _quantize_money(share.platform_fee),
        }
    return {
        "bank_fee": bank_fee,
        "remittance_profit": remittance_profit,
        "agent_fee": None,
        "capitalpay_profit": None,
    }


# ── 预下单 ─────────────────────────────────────────────────

class PreOrderRequestSerializer(serializers.Serializer):
    """预下单请求参数。"""
    merchant_no = serializers.CharField(max_length=32)
    merchant_order_no = serializers.CharField(max_length=64)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    currency = serializers.CharField(max_length=3, default="CNY")
    pay_method = serializers.ChoiceField(
        choices=[
            ("ONLINE_BANK", "Online Banking"),
            ("AUTHORIZED", "Authorized Payment"),
            ("WIRE_TRANSFER", "Wire Transfer"),
        ]
    )
    user_id = serializers.CharField(max_length=64, required=False, allow_blank=True)
    bank_code = serializers.CharField(max_length=16, required=False, allow_blank=True)
    notify_url = serializers.URLField(max_length=512, required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=64, required=False)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value


class PreOrderResponseSerializer(serializers.Serializer):
    """预下单返回。"""
    order_no = serializers.CharField()
    unique_identification_no = serializers.CharField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    fee_amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    status = serializers.CharField()
    expire_at = serializers.DateTimeField()
    created_at = serializers.DateTimeField()


# ── 订单查询 ───────────────────────────────────────────────

class PaymentOrderListSerializer(serializers.ModelSerializer):
    """订单列表 — 含汇款信息、审核信息。"""
    merchant_name = serializers.SerializerMethodField()
    merchant_no = serializers.SerializerMethodField()

    class Meta:
        model = PaymentOrder
        fields = [
            "id", "order_no", "merchant_order_no", "merchant_name", "merchant_no",
            "amount", "currency", "settle_amount", "from_currency", "to_currency", "fee_amount",
            "fee_currency", "sender_total_amount", "exchange_rate", "rate_source",
            "beneficiary_name", "beneficiary_bank", "beneficiary_account",
            "beneficiary_swift", "beneficiary_address",
            "remittance_purpose", "contract_file",
            "fee_bearing",
            "status", "pay_method", "unique_identification_no",
            "prn_code", "notify_status", "notify_count",
            "reviewed_by", "reviewed_at", "review_comment",
            "agent_review_status", "agent_reviewed_by", "agent_reviewed_at",
            "agent_review_comment",
            "agent_payout_request_status", "agent_payout_requested_by",
            "agent_payout_requested_at",
            "completed_at", "created_at",
        ]

    def get_merchant_name(self, obj):
        return obj.party_name

    def get_merchant_no(self, obj):
        return obj.party_no


def _timeline_step(code, title, at, verified=False, active=False):
    return {
        "code": code,
        "title": title,
        "at": at.isoformat() if at else "",
        "verified": verified,
        "active": active,
    }


def _has_agent_review_step(order):
    agent_status = getattr(order, "agent_review_status", "") or PaymentOrder.AgentReviewStatus.NONE
    return (
        order.status == PaymentOrder.OrderStatus.PENDING_AGENT_REVIEW
        or agent_status in {
            PaymentOrder.AgentReviewStatus.PENDING,
            PaymentOrder.AgentReviewStatus.APPROVED,
            PaymentOrder.AgentReviewStatus.REJECTED,
        }
    )


def _has_agent_payout_step(order):
    payout_status = getattr(
        order, "agent_payout_request_status", "",
    ) or PaymentOrder.AgentPayoutRequestStatus.NONE
    return payout_status in {
        PaymentOrder.AgentPayoutRequestStatus.PENDING,
        PaymentOrder.AgentPayoutRequestStatus.REQUESTED,
    }


def build_order_timeline(order):
    status = order.status
    agent_status = getattr(order, "agent_review_status", "") or PaymentOrder.AgentReviewStatus.NONE
    payout_status = getattr(
        order, "agent_payout_request_status", "",
    ) or PaymentOrder.AgentPayoutRequestStatus.NONE
    canonical = PaymentOrder.canonical_status(status)
    ops_reached = {
        "PENDING_PAY", "PAY_RECEIVED", "PENDING_SETTLE", "SETTLED",
        "REFUNDING", "REFUNDED",
    }
    review_verified = bool(order.reviewed_at) or canonical in ops_reached
    review_active = canonical == "PENDING_REVIEW"
    collection_verified = bool(order.pay_received_at) or canonical in {
        "PAY_RECEIVED", "PENDING_SETTLE", "SETTLED", "REFUNDING", "REFUNDED"
    }
    collection_active = canonical == "PENDING_PAY" and not order.pay_received_at
    awaiting_agent_payout = (
        canonical == "PAY_RECEIVED"
        and payout_status == PaymentOrder.AgentPayoutRequestStatus.PENDING
    )
    settlement_verified = bool(order.settled_at) or canonical in {"SETTLED", "REFUNDING", "REFUNDED"}
    settlement_active = (
        canonical in {"PAY_RECEIVED", "PENDING_SETTLE"}
        and not order.settled_at
        and not awaiting_agent_payout
    )
    completed_verified = (
        bool(order.completed_at)
        or bool(order.settled_at)
        or canonical in {"SETTLED", "REFUNDING", "REFUNDED"}
    )
    completed_active = False

    steps = [
        _timeline_step("submitted", "Instruction Submitted", order.created_at, verified=True),
    ]
    if _has_agent_review_step(order):
        agent_verified = bool(order.agent_reviewed_at) or agent_status in {
            PaymentOrder.AgentReviewStatus.APPROVED,
            PaymentOrder.AgentReviewStatus.REJECTED,
        }
        steps.append(_timeline_step(
            "agent_review",
            "Agent Review",
            order.agent_reviewed_at,
            verified=agent_verified,
            active=status == "PENDING_AGENT_REVIEW" or agent_status == PaymentOrder.AgentReviewStatus.PENDING,
        ))
    steps.extend([
        _timeline_step(
            "review", "Operations Review", order.reviewed_at,
            verified=review_verified, active=review_active,
        ),
        _timeline_step(
            "collection", "Collection Confirmed", order.pay_received_at,
            verified=collection_verified, active=collection_active,
        ),
    ])
    if _has_agent_payout_step(order):
        payout_verified = payout_status == PaymentOrder.AgentPayoutRequestStatus.REQUESTED or canonical in {
            "PENDING_SETTLE", "SETTLED", "REFUNDING", "REFUNDED",
        }
        steps.append(_timeline_step(
            "agent_payout_request",
            "Agent Requested Payout",
            getattr(order, "agent_payout_requested_at", None),
            verified=payout_verified,
            active=awaiting_agent_payout,
        ))
    steps.extend([
        _timeline_step(
            "settlement", "Settlement / Payout", order.settled_at,
            verified=settlement_verified, active=settlement_active,
        ),
        _timeline_step(
            "completed", "Completed", order.completed_at or order.settled_at,
            verified=completed_verified, active=completed_active,
        ),
    ])
    if status == "CLOSED":
        steps.append(_timeline_step("closed", "Closed", order.closed_at, verified=True, active=True))
    elif status in {"REFUNDING", "REFUNDED"}:
        steps.append(_timeline_step(
            "refunded",
            "Refunded" if status == "REFUNDED" else "Refund In Progress",
            order.updated_at,
            verified=status == "REFUNDED",
            active=status == "REFUNDING",
        ))
    return steps


class PaymentOrderSerializer(serializers.ModelSerializer):
    merchant_name = serializers.SerializerMethodField()

    class Meta:
        model = PaymentOrder
        fields = [
            "id", "order_no", "merchant_order_no", "merchant_name",
            "amount", "currency", "from_currency", "to_currency",
            "fee_amount", "fee_currency", "sender_total_amount",
            "settle_amount", "exchange_rate", "rate_source", "fee_bearing",
            "applied_fee_model", "applied_fee_rate", "applied_fixed_fee",
            "beneficiary_name", "beneficiary_bank", "beneficiary_swift",
            "beneficiary_account", "beneficiary_address",
            "remittance_purpose", "contract_file",
            "status", "pay_method", "bank_code", "payout_splits", "unique_identification_no",
            "prn_code",
            "notify_url", "notify_status", "notify_count", "last_notify_at",
            "pay_received_at", "settled_at", "closed_at", "expire_at",
            "reviewed_by", "reviewed_at", "review_comment",
            "agent_review_status", "agent_reviewed_by", "agent_reviewed_at",
            "agent_review_comment",
            "agent_payout_request_status", "agent_payout_requested_by",
            "agent_payout_requested_at",
            "quote",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "order_no", "merchant_order_no", "unique_identification_no",
            "created_at", "updated_at", "reviewed_by", "reviewed_at",
            "agent_review_status", "agent_reviewed_by", "agent_reviewed_at",
            "agent_review_comment",
            "agent_payout_request_status", "agent_payout_requested_by",
            "agent_payout_requested_at",
        ]

    def get_merchant_name(self, obj):
        return obj.party_name


class PaymentOrderDetailSerializer(PaymentOrderSerializer):
    merchant_no = serializers.SerializerMethodField()
    pay_method_display = serializers.CharField(source="get_pay_method_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    timeline = serializers.SerializerMethodField()
    quote_detail = serializers.SerializerMethodField()
    refunds = serializers.SerializerMethodField()
    bank_fee = serializers.SerializerMethodField()
    remittance_profit = serializers.SerializerMethodField()
    agent_fee = serializers.SerializerMethodField()
    capitalpay_profit = serializers.SerializerMethodField()

    class Meta(PaymentOrderSerializer.Meta):
        fields = PaymentOrderSerializer.Meta.fields + [
            "merchant_no", "user_id", "bank_txn_id", "completed_at",
            "status_history", "idempotency_key", "request_payload_hash",
            "pay_method_display", "status_display", "timeline", "quote_detail", "refunds",
            "bank_fee", "remittance_profit", "agent_fee", "capitalpay_profit",
        ]

    def _fee_breakdown(self, obj):
        cache = getattr(self, "_fee_breakdown_cache", None)
        if cache is None:
            cache = {}
            self._fee_breakdown_cache = cache
        key = str(getattr(obj, "pk", None) or id(obj))
        if key not in cache:
            cache[key] = resolve_order_fee_breakdown(obj)
        return cache[key]

    def _fee_field(self, obj, name):
        value = self._fee_breakdown(obj).get(name)
        return str(value) if value is not None else None

    def get_bank_fee(self, obj):
        return self._fee_field(obj, "bank_fee")

    def get_remittance_profit(self, obj):
        return self._fee_field(obj, "remittance_profit")

    def get_agent_fee(self, obj):
        return self._fee_field(obj, "agent_fee")

    def get_capitalpay_profit(self, obj):
        return self._fee_field(obj, "capitalpay_profit")

    def get_merchant_no(self, obj):
        return obj.party_no

    def get_timeline(self, obj):
        return build_order_timeline(obj)

    def get_quote_detail(self, obj):
        quote = getattr(obj, "quote", None)
        if not quote:
            return None
        return {
            "quote_no": quote.quote_no,
            "status": quote.status,
            "amount": quote.amount,
            "from_currency": quote.from_currency,
            "to_currency": quote.to_currency,
            "fee_bearing": quote.fee_bearing,
            "fee_amount": quote.fee_amount,
            "fee_currency": quote.fee_currency,
            "sender_fee_amount": quote.sender_fee_amount,
            "beneficiary_fee_amount": quote.beneficiary_fee_amount,
            "sender_total_amount": quote.sender_total_amount,
            "settle_amount": quote.settle_amount,
            "exchange_rate": quote.exchange_rate,
            "rate_source": quote.rate_source,
            "fee_model": quote.fee_model,
            "fee_rate": quote.fee_rate,
            "fixed_fee": quote.fixed_fee,
            "actor_type": quote.actor_type,
            "expires_at": quote.expires_at,
            "used_at": quote.used_at,
            "created_at": quote.created_at,
        }

    def get_refunds(self, obj):
        refunds = getattr(obj, "_prefetched_objects_cache", {}).get("refunds")
        if refunds is None:
            refunds = obj.refunds.all()
        return RefundOrderSerializer(refunds, many=True).data


# ── 汇款申请 ───────────────────────────────────────────────

class RemittanceQuoteRequestSerializer(serializers.Serializer):
    merchant = serializers.CharField(max_length=32, required=False, allow_blank=True)
    customer_id = serializers.CharField(max_length=64, required=False, allow_blank=True)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=0.01)
    from_currency = serializers.CharField(max_length=3, default="USD")
    to_currency = serializers.CharField(max_length=3, default="CNY")
    fee_bearing = serializers.ChoiceField(choices=["OUR", "SHA", "BEN"], default="OUR")

    def validate_from_currency(self, value):
        return value.upper()

    def validate_to_currency(self, value):
        return value.upper()


class RemittanceSubmitSerializer(serializers.Serializer):
    quote_id = serializers.CharField(max_length=40)
    customer_id = serializers.CharField(max_length=64, required=False, allow_blank=True)
    beneficiary_name = serializers.CharField(max_length=128, trim_whitespace=True)
    beneficiary_bank = serializers.CharField(max_length=128, trim_whitespace=True)
    beneficiary_account = serializers.CharField(max_length=64, trim_whitespace=True)
    beneficiary_swift = serializers.CharField(
        max_length=16, required=False, allow_blank=True, allow_null=True
    )
    beneficiary_address = serializers.CharField(
        max_length=256, required=False, allow_blank=True, allow_null=True
    )
    remittance_purpose = serializers.CharField(
        max_length=256, required=False, allow_blank=True, allow_null=True
    )
    contract_file = serializers.CharField(
        max_length=512, required=False, allow_blank=True, allow_null=True
    )
    pay_method = serializers.ChoiceField(
        choices=PaymentOrder.REMITTANCE_FUNDING_METHODS,
        default=PaymentOrder.PayMethod.WIRE_TRANSFER,
        required=False,
    )

    def validate(self, attrs):
        for field in (
            "beneficiary_swift", "beneficiary_address",
            "remittance_purpose", "contract_file",
        ):
            attrs[field] = attrs.get(field) or ""
        attrs["pay_method"] = attrs.get("pay_method") or PaymentOrder.PayMethod.WIRE_TRANSFER
        return attrs


class RemittanceApplySerializer(RemittanceSubmitSerializer):
    """向后兼容导入名；创建必须经 RemittanceApplicationService。"""


# ── 支付确认 ───────────────────────────────────────────────

class ManualConfirmSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    user_id = serializers.CharField(max_length=64)
    bank_txn_id = serializers.CharField(max_length=64, required=False, allow_blank=True)


# ── 退款 ───────────────────────────────────────────────────

class RefundRequestSerializer(serializers.Serializer):
    """退款申请请求。"""
    order_no = serializers.CharField(max_length=32)
    refund_amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    reason = serializers.CharField(max_length=256)
    idempotency_key = serializers.CharField(max_length=64, required=False)

    def validate_refund_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Refund amount must be greater than 0")
        return value


class RefundReviewSerializer(serializers.Serializer):
    """退款审核请求。"""
    action = serializers.ChoiceField(choices=[("approve", "Approve"), ("reject", "Reject")])
    reviewer = serializers.CharField(max_length=64)
    reason = serializers.CharField(max_length=256, required=False, allow_blank=True)


class RefundOrderSerializer(serializers.ModelSerializer):
    order_no = serializers.CharField(source="payment_order.order_no", read_only=True)
    merchant_name = serializers.SerializerMethodField()
    amount = serializers.DecimalField(source="payment_order.amount", max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = RefundOrder
        fields = [
            "id", "refund_no", "order_no", "merchant_name", "amount",
            "refund_amount", "refund_fee_rate", "refund_fee_amount", "refund_reason",
            "status", "reviewed_by", "reviewed_at", "refunded_at",
            "fail_reason", "bank_refund_id", "created_at",
        ]
        read_only_fields = fields

    def get_merchant_name(self, obj):
        order = obj.payment_order
        return order.party_name if order else ""


class BankCreditNotificationSerializer(serializers.ModelSerializer):
    """Ops list/detail for inbound bank credits matched by PRN."""

    class Meta:
        model = BankCreditNotification
        fields = [
            "id", "notification_no", "txn_id", "txn_time",
            "amount", "currency", "remark", "prn_code",
            "bank_code", "bank_name", "account_no",
            "order_no", "merchant_no", "merchant_name",
            "status", "source", "created_at",
        ]
        read_only_fields = fields


class BankCreditNotificationDetailSerializer(BankCreditNotificationSerializer):
    order_status = serializers.SerializerMethodField()
    expected_amount = serializers.SerializerMethodField()
    expected_currency = serializers.SerializerMethodField()
    collection_va = serializers.SerializerMethodField()
    raw_payload = serializers.JSONField(read_only=True)

    class Meta(BankCreditNotificationSerializer.Meta):
        fields = BankCreditNotificationSerializer.Meta.fields + [
            "order_status", "expected_amount", "expected_currency",
            "collection_va", "raw_payload",
        ]

    def get_order_status(self, obj):
        return obj.order.status if obj.order_id else ""

    def get_expected_amount(self, obj):
        if not obj.order_id:
            return ""
        return str(obj.order.expected_collection_amount())

    def get_expected_currency(self, obj):
        if not obj.order_id:
            return ""
        return obj.order.from_currency or obj.order.currency or ""

    def get_collection_va(self, obj):
        if not obj.order_id:
            return None
        from apps.payment.services.fund_trace import _serialize_va, resolve_collection_va

        return _serialize_va(resolve_collection_va(obj.order))


class SimulateBankCreditSerializer(serializers.Serializer):
    prn_code = serializers.CharField(max_length=32, required=False, allow_blank=True)
    order_no = serializers.CharField(max_length=32, required=False, allow_blank=True)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, allow_null=True)
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True)
    txn_id = serializers.CharField(max_length=64, required=False, allow_blank=True)
    txn_time = serializers.DateTimeField(required=False)
    remark = serializers.CharField(max_length=256, required=False, allow_blank=True)
    bank_code = serializers.CharField(max_length=16, required=False, allow_blank=True)
    bank_name = serializers.CharField(max_length=128, required=False, allow_blank=True)
    account_no = serializers.CharField(max_length=64, required=False, allow_blank=True)
    nostro_id = serializers.UUIDField(required=False, allow_null=True)
