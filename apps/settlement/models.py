"""清结算 — 模型定义。

对应功能清单:
    - 清算批次查询
    - 商户清算批次查询
    - 商户清算明细查询
    - nostro账户管理 / 资金调拨 (在 account app)
    - 手续费分润管理
    - 商户分账结算
    - 差异代销账管理
"""
from django.db import models
from apps.core.models import BaseModel


class SettlementBatch(BaseModel):
    """清算批次 — 按商户 + 日期生成。"""

    class SettleStatus(models.TextChoices):
        PENDING = "PENDING", "待清算"
        PROCESSING = "PROCESSING", "清算中"
        SETTLED = "SETTLED", "已清算"
        FAILED = "FAILED", "清算失败"

    batch_no = models.CharField(max_length=32, unique=True, verbose_name="清算批次号")
    settle_date = models.DateField(db_index=True, verbose_name="清算日期")
    merchant = models.ForeignKey(
        "merchant.Merchant", on_delete=models.PROTECT, related_name="settlement_batches", verbose_name="商户"
    )
    # ── 汇总统计 ──
    total_count = models.IntegerField(default=0, verbose_name="订单总笔数")
    total_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="订单总金额"
    )
    fee_total = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="手续费总额"
    )
    settle_net_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="净结算金额"
    )
    status = models.CharField(
        max_length=16, choices=SettleStatus.choices, default=SettleStatus.PENDING, verbose_name="状态"
    )
    settled_at = models.DateTimeField(null=True, verbose_name="清算完成时间")
    fail_reason = models.CharField(max_length=256, blank=True, verbose_name="失败原因")

    # ── 结算账户 ──
    settlement_account_info = models.JSONField(default=dict, verbose_name="结算账户信息快照")

    class Meta:
        db_table = "settlement_batch"
        verbose_name = "清算批次"
        verbose_name_plural = verbose_name
        ordering = ["-settle_date", "-created_at"]
        indexes = [
            models.Index(fields=["merchant", "settle_date"]),
            models.Index(fields=["status", "settle_date"]),
        ]


class SettlementDetail(BaseModel):
    """清算明细 — 每笔订单的清算记录。"""

    batch = models.ForeignKey(
        SettlementBatch, on_delete=models.CASCADE, related_name="details", verbose_name="清算批次"
    )
    payment_order = models.OneToOneField(
        "payment.PaymentOrder", on_delete=models.PROTECT, verbose_name="支付订单"
    )
    order_no = models.CharField(max_length=32, verbose_name="订单号")
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="订单金额")
    fee = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="手续费")
    settle_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="结算金额")

    class Meta:
        db_table = "settlement_detail"
        verbose_name = "清算明细"
        verbose_name_plural = verbose_name


class FeeShare(BaseModel):
    """手续费分润记录。

    功能清单对应: 手续费分润管理
    分账公式:
        channel_fee = 渠道手续费（银行收取）
        platform_gross = total_fee - channel_fee（平台毛利）
        agent_fee = platform_gross * commission_rate（代理商佣金）
        platform_fee = platform_gross - agent_fee（平台净收益）
    """

    settlement_detail = models.OneToOneField(
        SettlementDetail, on_delete=models.PROTECT, null=True, blank=True, verbose_name="清算明细"
    )
    payment_order = models.ForeignKey(
        "payment.PaymentOrder", on_delete=models.PROTECT,
        null=True, blank=True, related_name="fee_shares", verbose_name="汇款订单"
    )
    # ── 关联信息 ──
    agent = models.ForeignKey(
        "agent.Agent", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fee_shares", verbose_name="代理商"
    )
    # ── 冗余展示/筛选字段 ──
    order_no = models.CharField(max_length=32, default="", verbose_name="订单号")
    merchant_name = models.CharField(max_length=128, default="", verbose_name="商户名称")
    agent_name = models.CharField(max_length=128, default="", verbose_name="代理商名称")
    bank_channel_name = models.CharField(max_length=128, default="", verbose_name="银行渠道")
    amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="订单金额"
    )
    total_fee = models.DecimalField(
        max_digits=12, decimal_places=4, default=0, verbose_name="商户手续费总额"
    )
    # ── 分润金额 ──
    channel_fee = models.DecimalField(
        max_digits=12, decimal_places=4, default=0, verbose_name="渠道手续费"
    )
    platform_fee = models.DecimalField(
        max_digits=12, decimal_places=4, default=0, verbose_name="平台净收益"
    )
    agent_fee = models.DecimalField(
        max_digits=12, decimal_places=4, default=0, verbose_name="代理商佣金"
    )

    class Meta:
        db_table = "fee_share"
        verbose_name = "手续费分润"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["agent"]),
            models.Index(fields=["order_no"]),
            models.Index(fields=["merchant_name"]),
        ]


class DifferenceWriteOff(BaseModel):
    """差异代销账记录。

    功能清单对应: 差异代销账管理
    """

    class WriteOffStatus(models.TextChoices):
        PENDING = "PENDING", "待处理"
        APPROVED = "APPROVED", "已审批"
        WRITTEN_OFF = "WRITTEN_OFF", "已销账"
        REJECTED = "REJECTED", "已驳回"

    write_off_no = models.CharField(max_length=32, unique=True, verbose_name="销账单号")
    merchant = models.ForeignKey(
        "merchant.Merchant", on_delete=models.PROTECT, verbose_name="商户"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="销账金额")
    reason = models.CharField(max_length=256, verbose_name="原因")
    status = models.CharField(
        max_length=16, choices=WriteOffStatus.choices, default=WriteOffStatus.PENDING, verbose_name="状态"
    )
    applied_by = models.CharField(max_length=64, verbose_name="申请人")
    approved_by = models.CharField(max_length=64, blank=True, verbose_name="审批人")
    approved_at = models.DateTimeField(null=True, verbose_name="审批时间")

    class Meta:
        db_table = "difference_write_off"
        verbose_name = "差异代销账"
        verbose_name_plural = verbose_name
