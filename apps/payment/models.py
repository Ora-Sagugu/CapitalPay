"""支付交易模块 — 核心模型。"""
from decimal import Decimal
from django.db import models
from apps.core.models import BaseModel


class PaymentOrder(BaseModel):
    """支付订单 — 核心资金单据。

    主流程：
        PENDING_REVIEW → (审核通过) → PROCESSING → (自动完成) → COMPLETED
                       ↘ (驳回) → CLOSED
    退款流程：
        COMPLETED → REFUNDING → REFUNDED
    兼容旧流程：
        PRE_CREATE / PENDING_PAY / PAY_RECEIVED / PENDING_SETTLE / SETTLED
    """

    class OrderStatus(models.TextChoices):
        PRE_CREATE = "PRE_CREATE", "预创建"
        PENDING_REVIEW = "PENDING_REVIEW", "待审核"
        PROCESSING = "PROCESSING", "处理中"
        COMPLETED = "COMPLETED", "已完成"
        # 以下为兼容旧流程
        PENDING_PAY = "PENDING_PAY", "待收款"
        PAY_RECEIVED = "PAY_RECEIVED", "已收款"
        PENDING_SETTLE = "PENDING_SETTLE", "待清算"
        SETTLED = "SETTLED", "已清算"
        CLOSED = "CLOSED", "已关闭"
        REFUNDING = "REFUNDING", "退款中"
        REFUNDED = "REFUNDED", "已退款"

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

    # ── 金额（必须使用 Decimal） ──
    currency = models.CharField(max_length=3, default="CNY", verbose_name="币种")
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="订单金额")
    fee_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="手续费")
    settle_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="结算金额")

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

    # ── 支付方式 ──
    pay_method = models.CharField(max_length=32, choices=PayMethod.choices, verbose_name="支付方式")
    bank_code = models.CharField(max_length=16, null=True, blank=True, verbose_name="银行编码")
    bank_txn_id = models.CharField(max_length=64, null=True, blank=True, verbose_name="银行交易流水号")

    # ── 状态 ──
    status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.PRE_CREATE, verbose_name="状态"
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
            defaults={"fee_rate": 0.00, "updated_by": "system"},
        )
        return obj
# 注释
    @classmethod
    def get_fee_rate(cls) -> Decimal:
        """获取当前费率。"""
        return cls.get_config().fee_rate


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
