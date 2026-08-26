"""支付交易 — DRF 序列化器。"""
from rest_framework import serializers
from .models import PaymentOrder, RefundOrder
from apps.merchant.models import Merchant


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
    bank_code = serializers.CharField(max_length=16, required=False, allow_blank=True)
    user_id = serializers.CharField(max_length=64, required=False, allow_blank=True)
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

class PaymentOrderSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.merchant_name", read_only=True)

    class Meta:
        model = PaymentOrder
        fields = [
            "id", "order_no", "merchant_order_no", "merchant_name",
            "amount", "currency", "from_currency", "to_currency",
            "fee_amount", "settle_amount", "fee_bearing",
            "beneficiary_name", "beneficiary_bank", "beneficiary_swift",
            "beneficiary_account", "beneficiary_address",
            "remittance_purpose", "contract_file",
            "status", "pay_method", "bank_code", "unique_identification_no",
            "prn_code",
            "pay_received_at", "settled_at", "closed_at", "expire_at",
            "reviewed_by", "reviewed_at", "review_comment",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "order_no", "merchant_order_no", "unique_identification_no",
                           "created_at", "updated_at", "reviewed_by", "reviewed_at"]


class PaymentOrderListSerializer(serializers.ModelSerializer):
    """订单列表 — 含汇款信息、审核信息。"""
    merchant_name = serializers.CharField(source="merchant.merchant_name", read_only=True)
    merchant_no = serializers.CharField(source="merchant.merchant_no", read_only=True)

    class Meta:
        model = PaymentOrder
        fields = [
            "id", "order_no", "merchant_order_no", "merchant_name", "merchant_no",
            "amount", "currency", "settle_amount", "from_currency", "to_currency", "fee_amount",
            "beneficiary_name", "beneficiary_bank", "beneficiary_account",
            "beneficiary_swift", "beneficiary_address",
            "remittance_purpose", "contract_file",
            "fee_bearing",
            "status", "pay_method", "unique_identification_no",
            "prn_code",
            "reviewed_by", "reviewed_at", "review_comment",
            "completed_at", "created_at",
        ]


# ── 汇款申请 ───────────────────────────────────────────────

class RemittanceApplySerializer(serializers.ModelSerializer):
    """汇款申请 — 客户提交汇款请求。
    
    merchant 字段接受 merchant_no（如 M20260003）而非主键 UUID。
    创建成功后状态为「待审核」，自动生成分润结算记录。
    PRN 码在审核通过、订单完成后才生成，提交时不生成。
    自动查询当日汇率计算到账金额。
    """

    merchant = serializers.SlugRelatedField(
        slug_field="merchant_no",
        queryset=Merchant.objects.all(),
        error_messages={"does_not_exist": "Merchant not found"},
    )

    # 选填字段：前端允许留空，故序列化器需放行空串
    beneficiary_swift = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    beneficiary_address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    remittance_purpose = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    contract_file = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = PaymentOrder
        fields = [
            "merchant", "from_currency", "to_currency", "amount",
            "fee_bearing", "beneficiary_name", "beneficiary_bank",
            "beneficiary_swift", "beneficiary_account", "beneficiary_address",
            "remittance_purpose", "contract_file", "pay_method",
        ]

    def create(self, validated_data):
        import uuid
        from datetime import datetime, timedelta
        from django.utils import timezone as tz

        merchant = validated_data["merchant"]
        # 商户状态 + 执照有效期校验
        if merchant.status != merchant.Status.ACTIVE:
            raise serializers.ValidationError({"merchant": "Merchant is not active"})
        from datetime import date as date_cls
        if merchant.license_expiry_date and merchant.license_expiry_date < date_cls.today():
            raise serializers.ValidationError({
                "merchant": "Merchant business license has expired; remittance is restricted"
            })

        amount = float(validated_data["amount"])
        from_currency = validated_data.get("from_currency", "USD")
        to_currency = validated_data.get("to_currency", "CNY")

        fee_rate_pct = float(merchant.fee_rate or 0)
        fixed_fee = float(merchant.fixed_fee or 0)

        # 手续费 = 固定手续费 + (汇款金额 × 手续费率)
        percentage_fee = round(amount * fee_rate_pct / 100, 2)
        fee_amount = round(percentage_fee + fixed_fee, 2)

        # 查询当日汇率
        from apps.exchange.models import ExchangeRate
        today = tz.now().date()
        try:
            rate_obj = ExchangeRate.objects.get(
                date=today, from_currency=from_currency, to_currency=to_currency, is_deleted=False
            )
            exchange_rate = float(rate_obj.rate)
        except ExchangeRate.DoesNotExist:
            exchange_rate = None

        # 到账金额 = 汇款金额 × 汇率 - 手续费（如有汇率）
        if exchange_rate:
            settle_amount = round(amount * exchange_rate - fee_amount, 2)
        else:
            settle_amount = round(amount - fee_amount, 2)

        now = tz.now()
        order = PaymentOrder(
            order_no=f"RMT{now.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}",
            merchant_order_no=f"M{now.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}",
            unique_identification_no=f"PRN{now.strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}",
            idempotency_key=f"RMT{now.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}",
            merchant=merchant,
            amount=amount,
            currency=to_currency,
            from_currency=from_currency,
            to_currency=to_currency,
            fee_bearing=validated_data.get("fee_bearing", "OUR"),
            beneficiary_name=validated_data.get("beneficiary_name", ""),
            beneficiary_bank=validated_data.get("beneficiary_bank", ""),
            beneficiary_swift=validated_data.get("beneficiary_swift", ""),
            beneficiary_account=validated_data.get("beneficiary_account", ""),
            beneficiary_address=validated_data.get("beneficiary_address", ""),
            remittance_purpose=validated_data.get("remittance_purpose", ""),
            contract_file=validated_data.get("contract_file", ""),
            pay_method=validated_data.get("pay_method", "WIRE_TRANSFER"),
            fee_amount=fee_amount,
            settle_amount=settle_amount,
            status="PENDING_REVIEW",
            expire_at=now + timedelta(days=7),
        )
        order.status_history = [{"status": "PENDING_REVIEW", "time": now.isoformat()}]
        order.save()

        # ── 提交后自动生成分润结算记录 ──
        self._create_fee_share(order)

        return order

    def _create_fee_share(self, order):
        """提交汇款申请后自动生成分润记录。"""
        import logging
        logger = logging.getLogger(__name__)
        from apps.settlement.engine.calculator import SettlementCalculator
        try:
            calculator = SettlementCalculator()
            calculator.calculate_fee_share(order)
        except Exception as e:
            logger.warning("FeeShare 创建失败 (order=%s): %s", order.order_no, e)


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
    merchant_name = serializers.CharField(source="payment_order.merchant.merchant_name", read_only=True, default="")
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
