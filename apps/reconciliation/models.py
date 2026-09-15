"""对账引擎 — 模型定义。

对应功能清单:
    - 合作银行对账进度查询
    - 合作银行对账结果查询
    - 合作银行对账差错处理
    - 银行对账文件获取
    - 银行汇款交易核对
    - 银行汇款资金清算核对
    - 交易对账差错处理
    - 资金对账差错处理
    - nostro账户余额核对
"""
from django.db import models
from apps.core.models import BaseModel


class ReconciliationBatch(BaseModel):
    """对账批次 — 每日对账的执行记录。"""

    class BatchStatus(models.TextChoices):
        PENDING = "PENDING", "待执行"
        FETCHING = "FETCHING", "获取文件中"
        MATCHING = "MATCHING", "匹配中"
        MATCHED = "MATCHED", "已匹配"
        DIFF = "DIFF", "存在差异"
        RESOLVED = "RESOLVED", "差异已处理"

    batch_no = models.CharField(max_length=32, unique=True, verbose_name="对账批次号")
    bank_code = models.CharField(max_length=16, verbose_name="银行编码")
    bank_name = models.CharField(max_length=128, blank=True, verbose_name="银行名称")
    reconciliation_date = models.DateField(db_index=True, verbose_name="对账日")
    recon_type = models.CharField(
        max_length=24, default="TRANSACTION", db_index=True, verbose_name="对账类型"
    )  # TRANSACTION / SETTLEMENT_FUND

    # ── 对账文件 ──
    statement_file = models.CharField(max_length=512, blank=True, verbose_name="银行对账单文件路径")

    # ── 银行端统计 ──
    total_count_bank = models.IntegerField(default=0, verbose_name="银行端总笔数")
    total_amount_bank = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="银行端总金额"
    )

    # ── 平台端统计 ──
    total_count_platform = models.IntegerField(default=0, verbose_name="平台端总笔数")
    total_amount_platform = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="平台端总金额"
    )

    # ── 匹配结果 ──
    match_count = models.IntegerField(default=0, verbose_name="匹配成功笔数")
    match_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="匹配成功金额"
    )
    diff_count = models.IntegerField(default=0, verbose_name="差异笔数")
    diff_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="差异金额"
    )

    status = models.CharField(
        max_length=16, choices=BatchStatus.choices, default=BatchStatus.PENDING, verbose_name="状态"
    )

    started_at = models.DateTimeField(null=True, verbose_name="开始时间")
    completed_at = models.DateTimeField(null=True, verbose_name="完成时间")

    class Meta:
        db_table = "reconciliation_batch"
        verbose_name = "对账批次"
        verbose_name_plural = verbose_name
        ordering = ["-reconciliation_date", "-created_at"]
        indexes = [
            models.Index(fields=["bank_code", "reconciliation_date"]),
        ]


class ReconciliationDiff(BaseModel):
    """对账差异记录。"""

    class DiffType(models.TextChoices):
        BANK_ONLY = "BANK_ONLY", "银行有平台无"
        PLATFORM_ONLY = "PLATFORM_ONLY", "平台有银行无"
        AMOUNT_DIFF = "AMOUNT_DIFF", "金额不一致"
        STATUS_DIFF = "STATUS_DIFF", "状态不一致"

    class ResolutionType(models.TextChoices):
        PENDING = "PENDING", "待处理"
        ADJUST_BANK = "ADJUST_BANK", "以银行为准"
        ADJUST_PLATFORM = "ADJUST_PLATFORM", "以平台为准"
        MANUAL_CHECK = "MANUAL_CHECK", "人工核查"
        IGNORED = "IGNORED", "忽略"

    batch = models.ForeignKey(
        ReconciliationBatch, on_delete=models.CASCADE, related_name="diffs", verbose_name="对账批次"
    )
    diff_type = models.CharField(
        max_length=16, choices=DiffType.choices, verbose_name="差异类型"
    )
    order_no = models.CharField(max_length=32, null=True, blank=True, verbose_name="平台订单号")
    prn_code = models.CharField(max_length=6, null=True, blank=True, verbose_name="PRN码")
    bank_txn_id = models.CharField(max_length=64, null=True, blank=True, verbose_name="银行交易流水号")
    txn_time = models.DateTimeField(null=True, blank=True, verbose_name="交易时间")
    amount_bank = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, verbose_name="银行端金额"
    )
    amount_platform = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, verbose_name="平台端金额"
    )
    resolution = models.CharField(
        max_length=16, choices=ResolutionType.choices,
        default=ResolutionType.PENDING, verbose_name="处理方式"
    )
    resolution_note = models.TextField(blank=True, verbose_name="处理备注")
    resolved_by = models.CharField(max_length=64, blank=True, verbose_name="处理人")
    resolved_at = models.DateTimeField(null=True, verbose_name="处理时间")

    class Meta:
        db_table = "reconciliation_diff"
        verbose_name = "对账差异"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]


class NostroBalanceCheck(BaseModel):
    """Nostro 余额核对记录。"""

    check_date = models.DateField(verbose_name="核对日期")
    nostro_account = models.ForeignKey(
        "account.NostroAccount", on_delete=models.PROTECT, verbose_name="Nostro账户"
    )
    platform_balance = models.DecimalField(
        max_digits=18, decimal_places=2, verbose_name="平台账面余额"
    )
    bank_statement_balance = models.DecimalField(
        max_digits=18, decimal_places=2, verbose_name="银行对账单余额"
    )
    difference = models.DecimalField(
        max_digits=18, decimal_places=2, verbose_name="差额"
    )
    is_balanced = models.BooleanField(default=True, verbose_name="是否平衡")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "nostro_balance_check"
        verbose_name = "Nostro余额核对"
        verbose_name_plural = verbose_name
        ordering = ["-check_date"]


class ReconAlertConfig(BaseModel):
    """对账差异预警配置（单例）。"""

    enabled = models.BooleanField(default=True, verbose_name="是否启用")
    webhook_url = models.CharField(max_length=512, blank=True, verbose_name="Webhook URL")
    email = models.EmailField(blank=True, verbose_name="告警邮箱")

    class Meta:
        db_table = "recon_alert_config"
        verbose_name = "对账预警配置"
        verbose_name_plural = verbose_name

    @classmethod
    def get_config(cls) -> "ReconAlertConfig":
        obj, _ = cls.objects.get_or_create(
            is_deleted=False,
            defaults={"enabled": True, "webhook_url": "", "email": ""},
        )
        return obj


class ReconAlert(BaseModel):
    """对账差异预警 — 站内通知，并可投递 Webhook / 邮件。"""

    class Severity(models.TextChoices):
        WARNING = "WARNING", "警告"
        CRITICAL = "CRITICAL", "严重"

    class Channel(models.TextChoices):
        IN_APP = "IN_APP", "站内"
        WEBHOOK = "WEBHOOK", "Webhook"
        EMAIL = "EMAIL", "邮件"

    class AlertStatus(models.TextChoices):
        OPEN = "OPEN", "待确认"
        ACKED = "ACKED", "已确认"

    batch = models.ForeignKey(
        ReconciliationBatch, on_delete=models.CASCADE, related_name="alerts", verbose_name="对账批次"
    )
    severity = models.CharField(
        max_length=16, choices=Severity.choices, default=Severity.WARNING, verbose_name="级别"
    )
    title = models.CharField(max_length=128, verbose_name="标题")
    summary = models.TextField(blank=True, verbose_name="摘要")
    channel = models.CharField(
        max_length=16, choices=Channel.choices, default=Channel.IN_APP, verbose_name="渠道"
    )
    status = models.CharField(
        max_length=16, choices=AlertStatus.choices, default=AlertStatus.OPEN, verbose_name="状态"
    )
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="投递时间")
    delivery_error = models.CharField(max_length=256, blank=True, verbose_name="投递失败原因")
    acked_by = models.CharField(max_length=64, blank=True, verbose_name="确认人")
    acked_at = models.DateTimeField(null=True, blank=True, verbose_name="确认时间")

    class Meta:
        db_table = "recon_alert"
        verbose_name = "对账预警"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
