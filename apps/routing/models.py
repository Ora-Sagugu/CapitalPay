import uuid
from typing import Optional
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class BankChannel(models.Model):
    """银行通道"""

    class Status(models.TextChoices):
        ACTIVE = "active", "正常"
        SUSPENDED = "suspended", "暂停"
        MAINTENANCE = "maintenance", "维护中"
        OFFLINE = "offline", "下线"

    class ChannelType(models.TextChoices):
        ONLINE = "online", "网银支付"
        WIRE = "wire", "电汇"
        ACH = "ach", "ACH转账"
        REALTIME = "realtime", "实时支付"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bank_code = models.CharField("银行代码", max_length=20, unique=True)
    bank_name = models.CharField("银行名称", max_length=100)
    channel_type = models.CharField("通道类型", max_length=20, choices=ChannelType.choices, default=ChannelType.ONLINE)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.ACTIVE)
    priority = models.IntegerField("优先级", default=100, validators=[MinValueValidator(1), MaxValueValidator(999)])
    success_rate = models.DecimalField("成功率", max_digits=5, decimal_places=2, default=99.00)
    avg_response_time = models.IntegerField("平均响应时间(ms)", default=500)
    daily_limit = models.DecimalField("日限额", max_digits=18, decimal_places=2, default=999999999.99)
    fee_rate = models.DecimalField("手续费率", max_digits=5, decimal_places=4, default=0.0010)
    min_fee = models.DecimalField("最低手续费", max_digits=12, decimal_places=2, default=1.00)
    max_fee = models.DecimalField("最高手续费", max_digits=12, decimal_places=2, default=500.00)
    country = models.CharField("国家", max_length=50, blank=True, default="")
    usd_balance = models.DecimalField("USD余额", max_digits=18, decimal_places=2, default=0)
    hkd_balance = models.DecimalField("HKD余额", max_digits=18, decimal_places=2, default=0)
    cny_balance = models.DecimalField("CNY余额", max_digits=18, decimal_places=2, default=0)
    api_endpoint = models.URLField("API端点", blank=True)
    health_check_url = models.URLField("健康检查URL", blank=True)
    supported_currencies = models.JSONField("支持币种", default=list)
    supported_countries = models.JSONField("支持国家", default=list)
    remark = models.TextField("备注", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "routing_bank_channel"
        verbose_name = "银行通道"
        verbose_name_plural = "银行通道"
        ordering = ["priority", "bank_code"]

    def __str__(self) -> str:
        return f"{self.bank_name} ({self.bank_code})"


class BankTransaction(models.Model):
    """银行汇款记录 — 展示各银行的历史交易流水。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bank = models.ForeignKey(
        BankChannel, on_delete=models.CASCADE, related_name="transactions", verbose_name="银行"
    )
    txn_date = models.DateTimeField("交易日期", db_index=True)
    prn = models.CharField("PRN", max_length=32, db_index=True)
    beneficiary_name = models.CharField("收款人姓名", max_length=128)
    amount = models.DecimalField("金额", max_digits=18, decimal_places=2, default=0)
    currency = models.CharField("币种", max_length=3, default="USD")
    fee = models.DecimalField("手续费", max_digits=18, decimal_places=2, default=0)
    balance = models.DecimalField("余额", max_digits=18, decimal_places=2, default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "bank_transaction"
        verbose_name = "银行汇款记录"
        verbose_name_plural = "银行汇款记录"
        ordering = ["-txn_date"]

    def __str__(self) -> str:
        return f"{self.bank.bank_name} {self.prn} {self.amount} {self.currency}"


class RoutingRule(models.Model):
    """路由规则"""

    class RuleType(models.TextChoices):
        AMOUNT = "amount", "按金额"
        CURRENCY = "currency", "按币种"
        COUNTRY = "country", "按国家"
        PRIORITY = "priority", "按优先级"
        COST = "cost", "按成本"
        SUCCESS_RATE = "success_rate", "按成功率"
        BALANCED = "balanced", "负载均衡"

    class Status(models.TextChoices):
        ACTIVE = "active", "启用"
        INACTIVE = "inactive", "停用"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("规则名称", max_length=100)
    rule_type = models.CharField("规则类型", max_length=20, choices=RuleType.choices, default=RuleType.PRIORITY)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.ACTIVE)
    priority = models.IntegerField("优先级", default=100, validators=[MinValueValidator(1), MaxValueValidator(999)])
    conditions = models.JSONField("条件配置", default=dict)
    target_channels = models.ManyToManyField(BankChannel, verbose_name="目标通道", blank=True)
    fallback_channel = models.ForeignKey(
        BankChannel, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fallback_rules", verbose_name="兜底通道"
    )
    weight = models.IntegerField("权重", default=100, validators=[MinValueValidator(1), MaxValueValidator(100)])
    description = models.TextField("描述", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "routing_rule"
        verbose_name = "路由规则"
        verbose_name_plural = "路由规则"
        ordering = ["priority", "name"]

    def __str__(self) -> str:
        return self.name


class RoutingLog(models.Model):
    """路由日志"""

    class Result(models.TextChoices):
        SUCCESS = "success", "成功"
        FAILED = "failed", "失败"
        RETRY = "retry", "重试"
        TIMEOUT = "timeout", "超时"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_no = models.CharField("订单号", max_length=64, blank=True)
    rule = models.ForeignKey(RoutingRule, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="匹配规则")
    channel = models.ForeignKey(BankChannel, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="选择通道")
    amount = models.DecimalField("金额", max_digits=18, decimal_places=2, default=0)
    currency = models.CharField("币种", max_length=10, default="CNY")
    result = models.CharField("结果", max_length=20, choices=Result.choices, default=Result.SUCCESS)
    response_time = models.IntegerField("响应时间(ms)", default=0)
    error_message = models.TextField("错误信息", blank=True)
    request_data = models.JSONField("请求数据", default=dict)
    response_data = models.JSONField("响应数据", default=dict)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "routing_log"
        verbose_name = "路由日志"
        verbose_name_plural = "路由日志"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.order_no} -> {self.channel}"
