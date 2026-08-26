import uuid
from typing import Optional
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class CoopBank(models.Model):
    """合作银行"""

    class Status(models.TextChoices):
        ACTIVE = "active", "正常合作"
        SUSPENDED = "suspended", "暂停合作"
        TERMINATED = "terminated", "终止合作"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bank_code = models.CharField("银行代码", max_length=20, unique=True)
    bank_name = models.CharField("银行名称", max_length=100)
    bank_name_en = models.CharField("银行英文名称", max_length=100, blank=True)
    swift_code = models.CharField("SWIFT代码", max_length=20, blank=True)
    country = models.CharField("国家/地区", max_length=50, default="中国")
    city = models.CharField("城市", max_length=50, blank=True)
    address = models.TextField("地址", blank=True)
    contact_person = models.CharField("联系人", max_length=50, blank=True)
    contact_phone = models.CharField("联系电话", max_length=30, blank=True)
    contact_email = models.EmailField("联系邮箱", blank=True)
    status = models.CharField("合作状态", max_length=20, choices=Status.choices, default=Status.ACTIVE)
    settlement_cycle = models.IntegerField("结算周期(天)", default=1, validators=[MinValueValidator(0), MaxValueValidator(365)])
    daily_limit = models.DecimalField("日限额", max_digits=18, decimal_places=2, default=999999999.99)
    support_wire = models.BooleanField("支持电汇", default=True)
    support_ach = models.BooleanField("支持ACH", default=False)
    support_realtime = models.BooleanField("支持实时支付", default=False)
    nostro_account = models.CharField("Nostro账户号", max_length=50, blank=True)
    nostro_currency = models.CharField("Nostro币种", max_length=10, default="CNY")
    remark = models.TextField("备注", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "param_coop_bank"
        verbose_name = "合作银行"
        verbose_name_plural = "合作银行"
        ordering = ["bank_code"]

    def __str__(self) -> str:
        return f"{self.bank_name} ({self.bank_code})"


class FeeModel(models.Model):
    """手续费模型"""

    class FeeType(models.TextChoices):
        FIXED = "fixed", "固定费率"
        TIERED = "tiered", "阶梯费率"
        MIXED = "mixed", "混合费率"

    class Status(models.TextChoices):
        ACTIVE = "active", "启用"
        INACTIVE = "inactive", "停用"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model_code = models.CharField("模型代码", max_length=30, unique=True)
    model_name = models.CharField("模型名称", max_length=100)
    fee_type = models.CharField("费率类型", max_length=20, choices=FeeType.choices, default=FeeType.FIXED)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.ACTIVE)
    base_rate = models.DecimalField("基础费率", max_digits=7, decimal_places=6, default=0.003000)
    min_fee = models.DecimalField("最低手续费", max_digits=12, decimal_places=2, default=1.00)
    max_fee = models.DecimalField("最高手续费", max_digits=12, decimal_places=2, default=500.00)
    tier_config = models.JSONField("阶梯配置", default=dict, blank=True)
    description = models.TextField("描述", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "param_fee_model"
        verbose_name = "手续费模型"
        verbose_name_plural = "手续费模型"
        ordering = ["model_code"]

    def __str__(self) -> str:
        return self.model_name


class BankFeeConfig(models.Model):
    """合作银行支付手续费配置"""

    class Status(models.TextChoices):
        ACTIVE = "active", "启用"
        INACTIVE = "inactive", "停用"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bank = models.ForeignKey(CoopBank, on_delete=models.CASCADE, verbose_name="合作银行")
    fee_model = models.ForeignKey(FeeModel, on_delete=models.CASCADE, verbose_name="手续费模型")
    channel_type = models.CharField("通道类型", max_length=20, choices=[
        ("online", "网银支付"),
        ("wire", "电汇"),
        ("ach", "ACH转账"),
        ("realtime", "实时支付")
    ], default="online")
    override_rate = models.DecimalField("覆盖费率", max_digits=7, decimal_places=6, null=True, blank=True)
    override_min_fee = models.DecimalField("覆盖最低手续费", max_digits=12, decimal_places=2, null=True, blank=True)
    override_max_fee = models.DecimalField("覆盖最高手续费", max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.ACTIVE)
    effective_date = models.DateField("生效日期", blank=True, null=True)
    expiry_date = models.DateField("失效日期", blank=True, null=True)
    remark = models.TextField("备注", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "param_bank_fee_config"
        verbose_name = "银行手续费配置"
        verbose_name_plural = "银行手续费配置"
        unique_together = [["bank", "fee_model", "channel_type"]]
        ordering = ["bank", "channel_type"]

    def __str__(self) -> str:
        return f"{self.bank.bank_name} - {self.fee_model.model_name}"
