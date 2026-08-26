"""财务报表 — 模型定义。

功能清单对应:
    - 商户结算明细表
    - 商户结算批次表
    - 渠道手续费结算表
    - 商户日收单报表
    - 平台订单汇总表
"""
from django.db import models
from apps.core.models import BaseModel


class MerchantDailyReport(BaseModel):
    """商户日收单报表。"""

    report_date = models.DateField(db_index=True, verbose_name="报表日期")
    merchant = models.ForeignKey(
        "merchant.Merchant", on_delete=models.PROTECT, verbose_name="商户"
    )
    total_orders = models.IntegerField(default=0, verbose_name="订单笔数")
    total_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="订单总金额"
    )
    total_fee = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="手续费总额"
    )
    total_refunds = models.IntegerField(default=0, verbose_name="退款笔数")
    total_refund_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="退款总金额"
    )
    net_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="净收单金额"
    )

    class Meta:
        db_table = "merchant_daily_report"
        unique_together = [["report_date", "merchant"]]
        verbose_name = "商户日收单报表"
        verbose_name_plural = verbose_name


class ChannelFeeReport(BaseModel):
    """渠道手续费结算表。"""

    report_date = models.DateField(db_index=True, verbose_name="报表日期")
    bank_code = models.CharField(max_length=16, verbose_name="银行编码")
    bank_name = models.CharField(max_length=128, verbose_name="银行名称")
    total_orders = models.IntegerField(default=0, verbose_name="订单笔数")
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="交易总金额")
    channel_fee = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="渠道手续费")
    platform_fee = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="平台手续费")

    class Meta:
        db_table = "channel_fee_report"
        unique_together = [["report_date", "bank_code"]]
        verbose_name = "渠道手续费结算表"
        verbose_name_plural = verbose_name


class PlatformOrderSummary(BaseModel):
    """平台订单汇总表。"""

    report_date = models.DateField(unique=True, db_index=True, verbose_name="报表日期")
    total_merchants = models.IntegerField(default=0, verbose_name="活跃商户数")
    total_orders = models.IntegerField(default=0, verbose_name="总订单笔数")
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="总金额")
    total_fee = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="总手续费")
    total_refunds = models.IntegerField(default=0, verbose_name="总退款笔数")
    total_refund_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="总退款金额")
    settled_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="已清算金额")

    class Meta:
        db_table = "platform_order_summary"
        verbose_name = "平台订单汇总表"
        verbose_name_plural = verbose_name
