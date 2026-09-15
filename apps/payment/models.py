"""支付交易模块 — 核心模型。"""
from decimal import Decimal
from django.db import models
from apps.core.models import BaseModel


class RemittanceQuote(BaseModel):
    """可审计的汇款报价，提交订单时必须绑定且只能使用一次。"""

    class QuoteStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "有效"
        USED = "USED", "已使用"
        EXPIRED = "EXPIRED", "已过期"

    quote_no = models.CharField(max_length=40, unique=True, db_index=True, verbose_name="报价编号")
    merchant = models.ForeignKey(
        "merchant.Merchant", on_delete=models.PROTECT, related_name="remittance_quotes",
        verbose_name="商户",
    )
    user_id = models.CharField(max_length=64, blank=True, default="", verbose_name="客户用户ID")
    actor_type = models.CharField(
        max_length=16,
        choices=[("ADMIN", "运营"), ("CUSTOMER", "客户"), ("AGENT", "代理")],
        verbose_name="报价发起方",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="汇款本金")
    from_currency = models.CharField(max_length=3, verbose_name="汇出币种")
    to_currency = models.CharField(max_length=3, verbose_name="到账币种")
    fee_bearing = models.CharField(
        max_length=10,
        choices=[("OUR", "汇款人承担"), ("SHA", "双方共担"), ("BEN", "收款人承担")],
        verbose_name="费用承担方式",
    )
    fee_currency = models.CharField(max_length=3, verbose_name="手续费币种")
    fee_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="手续费")
    sender_fee_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="汇款方承担手续费"
    )
    beneficiary_fee_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="收款方承担手续费"
    )
    sender_total_amount = models.DecimalField(
        max_digits=18, decimal_places=2, verbose_name="汇款方应付总额"
    )
    settle_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="预计到账金额")
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8, verbose_name="使用汇率")
    rate_source = models.CharField(max_length=64, verbose_name="汇率来源")
    fee_model = models.CharField(max_length=16, verbose_name="费率模式")
    fee_rate = models.DecimalField(max_digits=8, decimal_places=6, default=0, verbose_name="费率快照")
    fixed_fee = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name="固定费快照")
    payload_hash = models.CharField(max_length=64, verbose_name="报价参数摘要")
    status = models.CharField(
        max_length=16, choices=QuoteStatus.choices, default=QuoteStatus.ACTIVE,
        verbose_name="报价状态",
    )
    expires_at = models.DateTimeField(db_index=True, verbose_name="报价过期时间")
    used_at = models.DateTimeField(null=True, blank=True, verbose_name="使用时间")

    class Meta:
        db_table = "remittance_quote"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(status__in=["ACTIVE", "USED", "EXPIRED"]),
                name="remittance_quote_valid_status",
            ),
        ]


class MerchantDailyRemittanceUsage(BaseModel):
    """商户每日汇款额度的原子预留记录。"""

    merchant = models.ForeignKey(
        "merchant.Merchant", on_delete=models.PROTECT, related_name="daily_remittance_usage",
        verbose_name="商户",
    )
    usage_date = models.DateField(verbose_name="业务日期")
    total_amount = models.DecimalField(
        max_digits=20, decimal_places=2, default=0, verbose_name="已预留汇款金额"
    )
    order_count = models.PositiveIntegerField(default=0, verbose_name="已预留订单数")

    class Meta:
        db_table = "merchant_daily_remittance_usage"
        constraints = [
            models.UniqueConstraint(
                fields=["merchant", "usage_date"],
                name="unique_merchant_daily_remittance_usage",
            ),
        ]


class PaymentOrder(BaseModel):
    """支付订单 — 核心资金单据。

    汇款主路径（写入这些代码）:
        PENDING_AGENT_REVIEW → (代理同意) → PENDING_REVIEW → (运营通过) → PENDING_PAY
                             ↘ (代理驳回) → CLOSED
        PENDING_REVIEW → (运营驳回) → CLOSED
        PENDING_PAY → (入金确认) → PAY_RECEIVED
            → (绑定 Agent 时须 Request payout) → (Confirm transfer) → PENDING_SETTLE
            → (结算批次) → SETTLED
        SETTLED → REFUNDING → REFUNDED

    遗留别名（可读、不再新写入）:
        PRE_CREATE / PROCESSING → 视同 PENDING_PAY
        COMPLETED → 视同 SETTLED
    """

    class OrderStatus(models.TextChoices):
        PENDING_AGENT_REVIEW = "PENDING_AGENT_REVIEW", "待代理审核"
        PENDING_REVIEW = "PENDING_REVIEW", "待运营审核"
        PENDING_PAY = "PENDING_PAY", "待入金"
        PAY_RECEIVED = "PAY_RECEIVED", "已入金"
        PENDING_SETTLE = "PENDING_SETTLE", "付款处理中"
        SETTLED = "SETTLED", "已完成"
        CLOSED = "CLOSED", "已关闭"
        REFUNDING = "REFUNDING", "退款中"
        REFUNDED = "REFUNDED", "已退款"
        # 遗留别名，仅兼容历史行
        PRE_CREATE = "PRE_CREATE", "待入金"
        PROCESSING = "PROCESSING", "待入金"
        COMPLETED = "COMPLETED", "已完成"

    LEGACY_STATUS_ALIASES = {
        "PRE_CREATE": "PENDING_PAY",
        "PROCESSING": "PENDING_PAY",
        "COMPLETED": "SETTLED",
    }

    @classmethod
    def canonical_status(cls, status: str) -> str:
        return cls.LEGACY_STATUS_ALIASES.get(status, status)

    class AgentReviewStatus(models.TextChoices):
        NONE = "none", "无需代理审核"
        PENDING = "pending", "待代理审核"
        APPROVED = "approved", "代理已同意"
        REJECTED = "rejected", "代理已驳回"

    class AgentPayoutRequestStatus(models.TextChoices):
        NONE = "none", "无需代理催促"
        PENDING = "pending", "待代理催促打款"
        REQUESTED = "requested", "代理已催促打款"

    class PayMethod(models.TextChoices):
        ONLINE_BANK = "ONLINE_BANK", "银行网银支付"
        AUTHORIZED = "AUTHORIZED", "账户授权支付"
        WIRE_TRANSFER = "WIRE_TRANSFER", "转款汇款"

    # ── 订单标识 ──
    order_no = models.CharField(max_length=32, unique=True, db_index=True, verbose_name="平台订单号")
    merchant_order_no = models.CharField(max_length=64, db_index=True, verbose_name="商户订单号")
    unique_identification_no = models.CharField(
        max_length=64, unique=True, db_index=True, verbose_name="汇款唯一识别号"
    )
    prn_code = models.CharField(
        max_length=32, unique=True, null=True, blank=True, db_index=True, verbose_name="PRN码"
    )

    # ── 关联 ──
    merchant = models.ForeignKey(
        "merchant.Merchant", on_delete=models.PROTECT, related_name="orders", verbose_name="商户"
    )
    user_id = models.CharField(max_length=64, null=True, blank=True, verbose_name="用户ID")
    quote = models.OneToOneField(
        RemittanceQuote, on_delete=models.PROTECT, null=True, blank=True,
        related_name="payment_order", verbose_name="汇款报价",
    )

    # ── 金额（必须使用 Decimal） ──
    currency = models.CharField(max_length=3, default="CNY", verbose_name="币种")
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="订单金额")
    fee_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="手续费")
    settle_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="结算金额")
    sender_total_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="汇款方应付总额"
    )
    fee_currency = models.CharField(max_length=3, blank=True, default="", verbose_name="手续费币种")
    exchange_rate = models.DecimalField(
        max_digits=18, decimal_places=8, null=True, blank=True, verbose_name="使用汇率"
    )
    rate_source = models.CharField(max_length=64, blank=True, default="", verbose_name="汇率来源")
    applied_fee_model = models.CharField(
        max_length=16, blank=True, default="", verbose_name="费率模式快照"
    )
    applied_fee_rate = models.DecimalField(
        max_digits=8, decimal_places=6, default=0, verbose_name="费率快照"
    )
    applied_fixed_fee = models.DecimalField(
        max_digits=12, decimal_places=4, default=0, verbose_name="固定费快照"
    )

    # ── 汇款专用字段 ──
    from_currency = models.CharField(max_length=3, default="USD", verbose_name="汇出币种")
    to_currency = models.CharField(max_length=3, default="CNY", verbose_name="到账币种")
    fee_bearing = models.CharField(
        max_length=10, default="OUR",
        choices=[("OUR", "汇款人承担"), ("SHA", "双方共担"), ("BEN", "收款人承担")],
        verbose_name="费用承担方式"
    )
    beneficiary_name = models.CharField(max_length=128, default="", verbose_name="收款人名称")
    beneficiary_bank = models.CharField(max_length=128, default="", verbose_name="收款银行")
    beneficiary_swift = models.CharField(max_length=16, default="", verbose_name="SWIFT代码")
    beneficiary_account = models.CharField(max_length=64, default="", verbose_name="收款账号")
    beneficiary_address = models.CharField(max_length=256, default="", verbose_name="收款人地址")
    remittance_purpose = models.CharField(max_length=256, default="", verbose_name="汇款用途")
    contract_file = models.CharField(max_length=512, blank=True, verbose_name="合同文件路径")

    # ── 审核 ──
    reviewed_by = models.CharField(max_length=64, null=True, blank=True, verbose_name="审核人")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="审核时间")
    review_comment = models.CharField(max_length=512, blank=True, verbose_name="审核意见")
    agent_review_status = models.CharField(
        max_length=16,
        choices=AgentReviewStatus.choices,
        default=AgentReviewStatus.NONE,
        db_index=True,
        verbose_name="代理审核状态",
    )
    agent_reviewed_by = models.CharField(max_length=64, blank=True, default="", verbose_name="代理审核人")
    agent_reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="代理审核时间")
    agent_review_comment = models.CharField(max_length=512, blank=True, default="", verbose_name="代理审核意见")
    agent_payout_request_status = models.CharField(
        max_length=16,
        choices=AgentPayoutRequestStatus.choices,
        default=AgentPayoutRequestStatus.NONE,
        db_index=True,
        verbose_name="代理催促打款状态",
    )
    agent_payout_requested_by = models.CharField(max_length=64, blank=True, default="", verbose_name="代理催促人")
    agent_payout_requested_at = models.DateTimeField(null=True, blank=True, verbose_name="代理催促时间")

    # ── 支付方式 ──
    pay_method = models.CharField(max_length=32, choices=PayMethod.choices, verbose_name="支付方式")
    bank_code = models.CharField(max_length=16, null=True, blank=True, verbose_name="银行编码")
    bank_txn_id = models.CharField(max_length=64, null=True, blank=True, verbose_name="银行交易流水号")

    # ── 状态 ──
    status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING_REVIEW, verbose_name="状态"
    )
    status_history = models.JSONField(default=list, verbose_name="状态历史")

    # ── 时间节点 ──
    pay_received_at = models.DateTimeField(null=True, blank=True, verbose_name="收款时间")
    settled_at = models.DateTimeField(null=True, blank=True, verbose_name="清算时间")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="关闭时间")
    expire_at = models.DateTimeField(verbose_name="过期时间")

    # ── 幂等 & 安全 ──
    idempotency_key = models.CharField(max_length=64, unique=True, db_index=True, verbose_name="幂等键")
    request_payload_hash = models.CharField(
        max_length=64, blank=True, default="", verbose_name="提交参数摘要"
    )
    signature = models.CharField(max_length=512, blank=True, verbose_name="请求签名")

    # ── 回调通知 ──
    notify_url = models.URLField(max_length=512, null=True, blank=True, verbose_name="通知地址")
    notify_count = models.IntegerField(default=0, verbose_name="通知次数")
    last_notify_at = models.DateTimeField(null=True, blank=True, verbose_name="最后通知时间")
    notify_status = models.CharField(
        max_length=16, default="PENDING", verbose_name="通知状态"
    )  # PENDING / SUCCESS / FAILED

    class Meta:
        db_table = "payment_order"
        verbose_name = "支付订单"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["merchant_order_no", "merchant"]),
            models.Index(fields=["user_id", "status"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["merchant", "pay_received_at"]),
        ]

    def __str__(self):
        return f"{self.order_no} - {self.amount}"

    def add_status_history(self, status: str, extra: dict = None):
        """追加状态历史。"""
        from django.utils import timezone
        entry = {"status": status, "time": timezone.now().isoformat()}
        if extra:
            entry.update(extra)
        self.status_history.append(entry)


class RefundOrder(BaseModel):
    """退款单。"""

    class RefundStatus(models.TextChoices):
        PENDING_REVIEW = "PENDING_REVIEW", "待审核"
        APPROVED = "APPROVED", "已通过"
        REJECTED = "REJECTED", "已驳回"
        PROCESSING = "PROCESSING", "处理中"
        SUCCESS = "SUCCESS", "退款成功"
        FAILED = "FAILED", "退款失败"

    refund_no = models.CharField(max_length=32, unique=True, db_index=True, verbose_name="退款单号")
    payment_order = models.ForeignKey(
        PaymentOrder, on_delete=models.PROTECT, related_name="refunds", verbose_name="原支付订单"
    )
    refund_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="退款金额")
    refund_fee_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, verbose_name="退款手续费率(%)"
    )
    refund_fee_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="退款手续费金额"
    )
    refund_reason = models.CharField(max_length=256, verbose_name="退款原因")
    status = models.CharField(
        max_length=20, choices=RefundStatus.choices, default=RefundStatus.PENDING_REVIEW, verbose_name="状态"
    )
    reviewed_by = models.CharField(max_length=64, null=True, blank=True, verbose_name="审核人")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="审核时间")
    bank_refund_id = models.CharField(max_length=64, null=True, blank=True, verbose_name="银行退款流水")
    refunded_at = models.DateTimeField(null=True, blank=True, verbose_name="退款完成时间")
    fail_reason = models.CharField(max_length=256, blank=True, verbose_name="失败原因")

    class Meta:
        db_table = "refund_order"
        verbose_name = "退款单"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]


class RefundFeeConfig(BaseModel):
    """退款手续费配置 — 单例模型，只有一条记录。"""

    fee_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        verbose_name="退款手续费率(%)",
        help_text="例如 1.50 表示 1.50%，退款金额 × 费率 = 手续费"
    )
    updated_by = models.CharField(max_length=64, blank=True, verbose_name="修改人")

    class Meta:
        db_table = "refund_fee_config"
        verbose_name = "退款手续费配置"
        verbose_name_plural = verbose_name

    @classmethod
    def get_config(cls) -> "RefundFeeConfig":
        """获取配置（单例），不存在则创建默认记录。"""
        obj, _ = cls.objects.get_or_create(
            is_deleted=False,
            defaults={"fee_rate": Decimal("0.00"), "updated_by": "system"},
        )
        return obj

    @classmethod
    def get_fee_rate(cls) -> Decimal:
        """获取当前费率。"""
        return Decimal(str(cls.get_config().fee_rate or 0))


class PRNConfig(BaseModel):
    """PRN 生成规则配置（单例）。

    支持前缀、主体长度、是否启用校验位、字符集，保证全局唯一与幂等。
    """

    class Charset(models.TextChoices):
        NUMERIC = "NUMERIC", "纯数字"
        ALNUM = "ALNUM", "数字+大写字母"

    prefix = models.CharField(max_length=8, default="", verbose_name="前缀")
    length = models.IntegerField(default=6, verbose_name="主体长度(不含前缀与校验位)")
    use_check_digit = models.BooleanField(default=False, verbose_name="是否启用校验位")
    charset = models.CharField(max_length=8, choices=Charset.choices, default=Charset.NUMERIC, verbose_name="字符集")
    updated_by = models.CharField(max_length=64, blank=True, verbose_name="修改人")

    class Meta:
        db_table = "prn_config"
        verbose_name = "PRN配置"
        verbose_name_plural = verbose_name

    @classmethod
    def get_config(cls) -> "PRNConfig":
        """获取配置（单例），不存在则创建默认记录。"""
        obj, _ = cls.objects.get_or_create(
            is_deleted=False,
            defaults={
                "prefix": "", "length": 6, "use_check_digit": False,
                "charset": cls.Charset.NUMERIC, "updated_by": "system",
            },
        )
        return obj


class PrnIssuance(BaseModel):
    """独立 PRN 签发记录 — 供代理系统 HMAC API 直接申请，不依赖运营审单。"""

    class Status(models.TextChoices):
        ISSUED = "ISSUED", "已签发"
        BOUND = "BOUND", "已绑定订单"
        MATCHED = "MATCHED", "已匹配收款"
        EXPIRED = "EXPIRED", "已过期"

    prn_code = models.CharField(max_length=32, unique=True, db_index=True, verbose_name="PRN码")
    agent = models.ForeignKey(
        "agent.Agent", on_delete=models.PROTECT, related_name="prn_issuances", verbose_name="代理商"
    )
    merchant = models.ForeignKey(
        "merchant.Merchant", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="prn_issuances", verbose_name="关联商户",
    )
    order = models.ForeignKey(
        PaymentOrder, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="prn_issuances", verbose_name="绑定订单",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, verbose_name="金额")
    currency = models.CharField(max_length=3, default="CNY", verbose_name="币种")
    reference = models.CharField(max_length=128, blank=True, verbose_name="业务参考号")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ISSUED, verbose_name="状态"
    )
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="过期时间")

    class Meta:
        db_table = "prn_issuance"
        verbose_name = "PRN签发"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.prn_code} ({self.status})"


class BankCreditNotification(BaseModel):
    """Inbound bank credit advice — mock ingest now, bank webhook later.

    Matching a PRN fills the remittance order and customer. This row does not
    confirm collection; Confirm payment on the order remains a separate step.
    """

    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "已接收"
        MATCHED = "MATCHED", "已匹配"
        MISMATCH = "MISMATCH", "金额不符"
        UNMATCHED = "UNMATCHED", "未匹配"

    class Source(models.TextChoices):
        MOCK = "MOCK", "模拟入金"
        BANK_API = "BANK_API", "银行接口"

    notification_no = models.CharField(max_length=40, unique=True, db_index=True, verbose_name="通知单号")
    txn_id = models.CharField(max_length=64, unique=True, db_index=True, verbose_name="银行流水号")
    txn_time = models.DateTimeField(db_index=True, verbose_name="入账时间")
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="入账金额")
    currency = models.CharField(max_length=3, verbose_name="币种")
    remark = models.CharField(max_length=256, blank=True, default="", verbose_name="银行附言")
    prn_code = models.CharField(max_length=32, blank=True, default="", db_index=True, verbose_name="PRN码")
    bank_code = models.CharField(max_length=16, blank=True, default="", db_index=True, verbose_name="入金银行编码")
    bank_name = models.CharField(max_length=128, blank=True, default="", verbose_name="入金银行")
    account_no = models.CharField(max_length=64, blank=True, default="", verbose_name="入金账号")
    order = models.ForeignKey(
        PaymentOrder, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="bank_credit_notifications", verbose_name="匹配订单",
    )
    merchant = models.ForeignKey(
        "merchant.Merchant", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="bank_credit_notifications", verbose_name="匹配客户",
    )
    order_no = models.CharField(max_length=32, blank=True, default="", db_index=True, verbose_name="订单号")
    merchant_no = models.CharField(max_length=32, blank=True, default="", verbose_name="客户编号")
    merchant_name = models.CharField(max_length=128, blank=True, default="", verbose_name="客户名称")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.RECEIVED, db_index=True, verbose_name="匹配状态"
    )
    source = models.CharField(
        max_length=16, choices=Source.choices, default=Source.MOCK, verbose_name="来源"
    )
    raw_payload = models.JSONField(default=dict, blank=True, verbose_name="原始报文")

    class Meta:
        db_table = "bank_credit_notification"
        verbose_name = "银行入金通知"
        verbose_name_plural = verbose_name
        ordering = ["-txn_time", "-created_at"]

    def __str__(self):
        return f"{self.notification_no} ({self.status})"
