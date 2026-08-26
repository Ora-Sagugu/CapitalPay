"""Agent models — 代理服务"""
from django.db import models
from django.utils import timezone
from apps.core.models import BaseModel


class Agent(BaseModel):
    """代理商/代理机构"""
    STATUS_CHOICES = (
        ("ACTIVE", "活跃"),
        ("SUSPENDED", "暂停"),
        ("CLOSED", "关闭"),
    )
    LEVEL_CHOICES = (
        ("LEVEL_1", "一级代理"),
        ("LEVEL_2", "二级代理"),
        ("LEVEL_3", "三级代理"),
    )
    agent_no = models.CharField("代理编号", max_length=32, unique=True, db_index=True)
    agent_name = models.CharField("代理名称", max_length=128)
    short_name = models.CharField("简称", max_length=64, blank=True)
    level = models.CharField("代理等级", max_length=16, choices=LEVEL_CHOICES, default="LEVEL_1")
    status = models.CharField("状态", max_length=16, choices=STATUS_CHOICES, default="ACTIVE")
    contact_name = models.CharField("联系人", max_length=64, blank=True)
    contact_phone = models.CharField("联系电话", max_length=20, blank=True)
    contact_email = models.EmailField("联系邮箱", blank=True)
    commission_rate = models.DecimalField("佣金比例", max_digits=8, decimal_places=6, default=0)
    max_merchant_count = models.IntegerField("最大商户数", default=0)  # 0=无限制

    # ── 尽调信息 ──
    legal_person = models.CharField("法人姓名", max_length=64, blank=True)
    id_type = models.CharField("证件类型", max_length=32, blank=True)
    legal_person_id = models.CharField("法人证件号", max_length=64, blank=True)
    business_license_no = models.CharField("营业执照号", max_length=64, blank=True)
    business_license_file = models.CharField("营业执照文件", max_length=512, blank=True)
    registered_capital = models.CharField("注册资本", max_length=64, blank=True)
    registered_address = models.CharField("注册地址", max_length=256, blank=True)
    business_scope = models.CharField("经营范围", max_length=512, blank=True)
    established_date = models.DateField("成立日期", null=True, blank=True)

    # ── 结算银行信息 ──
    settlement_bank_name = models.CharField("结算银行", max_length=128, blank=True)
    settlement_account_no = models.CharField("对公账户", max_length=64, blank=True)
    swift_code = models.CharField("SWIFT代码", max_length=16, blank=True)
    settlement_account_holder = models.CharField("账户持有人", max_length=128, blank=True)

    remark = models.TextField("备注", blank=True)

    class Meta:
        db_table = "agent"
        verbose_name = "代理商"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.agent_no} - {self.agent_name}"


class AgentMerchant(BaseModel):
    """代理-商户关联"""
    agent = models.ForeignKey(Agent, on_delete=models.PROTECT, related_name="merchant_relations", verbose_name="代理商")
    merchant = models.ForeignKey("merchant.Merchant", on_delete=models.PROTECT, related_name="agent_relations", verbose_name="商户")
    commission_rate = models.DecimalField("分佣比例", max_digits=8, decimal_places=6, default=0)
    effective_from = models.DateField("生效日期")
    effective_to = models.DateField("失效日期", null=True, blank=True)

    class Meta:
        db_table = "agent_merchant"
        verbose_name = "代理商户关联"
        verbose_name_plural = verbose_name
        unique_together = [("agent", "merchant")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.agent.agent_name} - {self.merchant.merchant_name}"


class AgentFeeConfig(BaseModel):
    """代理商费率配置 — 差异化手续费标准与分润比例"""
    FEE_TYPE_CHOICES = (
        ("TRANSACTION", "交易手续费"),
        ("SETTLEMENT", "结算手续费"),
        ("SERVICE", "服务费"),
    )
    CURRENCY_CHOICES = (
        ("USD", "美元"), ("EUR", "欧元"), ("GBP", "英镑"),
        ("CNY", "人民币"), ("JPY", "日元"), ("HKD", "港币"),
    )
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="fee_configs", verbose_name="代理商")
    fee_type = models.CharField("费用类型", max_length=16, choices=FEE_TYPE_CHOICES, default="TRANSACTION")
    currency = models.CharField("币种", max_length=4, choices=CURRENCY_CHOICES, default="USD")
    rate = models.DecimalField("费率(%)", max_digits=8, decimal_places=6, default=0,
                               help_text="百分比费率，如 0.5 表示 0.5%")
    fixed_fee = models.DecimalField("固定手续费", max_digits=14, decimal_places=2, default=0,
                                    help_text="每笔固定收取金额")
    min_amount = models.DecimalField("最低收费", max_digits=14, decimal_places=2, default=0)
    max_amount = models.DecimalField("最高收费", max_digits=14, decimal_places=2, default=0,
                                     help_text="0 表示不设上限")
    is_active = models.BooleanField("启用", default=True)
    remark = models.TextField("备注", blank=True)

    class Meta:
        db_table = "agent_fee_config"
        verbose_name = "代理商费率配置"
        verbose_name_plural = verbose_name
        unique_together = [("agent", "fee_type", "currency")]
        ordering = ["agent", "fee_type", "currency"]

    def __str__(self):
        return f"{self.agent.agent_name} — {self.get_fee_type_display()} — {self.currency}"


class AgentCommission(BaseModel):
    """代理佣金记录"""
    STATUS_CHOICES = (
        ("PENDING", "待结算"),
        ("SETTLED", "已结算"),
        ("PAID", "已支付"),
    )
    commission_no = models.CharField("佣金单号", max_length=32, unique=True, db_index=True)
    agent = models.ForeignKey(Agent, on_delete=models.PROTECT, related_name="commissions", verbose_name="代理商")
    merchant = models.ForeignKey("merchant.Merchant", on_delete=models.PROTECT, related_name="agent_commissions", verbose_name="商户")
    order_count = models.IntegerField("订单笔数", default=0)
    total_amount = models.DecimalField("交易总额", max_digits=18, decimal_places=2, default=0)
    commission_amount = models.DecimalField("佣金金额", max_digits=18, decimal_places=2, default=0)
    status = models.CharField("状态", max_length=16, choices=STATUS_CHOICES, default="PENDING")
    settle_date = models.DateField("结算日期", null=True, blank=True)
    paid_at = models.DateTimeField("支付时间", null=True, blank=True)
    remark = models.TextField("备注", blank=True)

    class Meta:
        db_table = "agent_commission"
        verbose_name = "代理佣金"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return self.commission_no


class AgentKYC(BaseModel):
    """代理 KYC 信息 — 分级尽调，审核流可追溯。

    状态机:
        PENDING → (提交) → SUBMITTED → (进入审核) → UNDER_REVIEW
               → (通过) → APPROVED | (驳回) → REJECTED
    """

    class KycStatus(models.TextChoices):
        PENDING = "PENDING", "待提交"
        SUBMITTED = "SUBMITTED", "已提交"
        UNDER_REVIEW = "UNDER_REVIEW", "审核中"
        APPROVED = "APPROVED", "通过"
        REJECTED = "REJECTED", "驳回"

    class KycTier(models.TextChoices):
        TIER_1 = "TIER_1", "一级(基础)"
        TIER_2 = "TIER_2", "二级(标准)"
        TIER_3 = "TIER_3", "三级(增强)"

    class IdType(models.TextChoices):
        ID_CARD = "ID_CARD", "身份证"
        PASSPORT = "PASSPORT", "护照"
        BUSINESS_LICENSE = "BUSINESS_LICENSE", "营业执照"

    agent = models.OneToOneField(
        Agent, on_delete=models.CASCADE, related_name="kyc", verbose_name="代理商"
    )
    tier = models.CharField(max_length=8, choices=KycTier.choices, default=KycTier.TIER_1, verbose_name="KYC等级")
    legal_person = models.CharField(max_length=64, verbose_name="法人姓名")
    id_type = models.CharField(
        max_length=16, choices=IdType.choices, default=IdType.BUSINESS_LICENSE, verbose_name="证件类型"
    )
    id_number = models.CharField(max_length=256, verbose_name="证件号(加密)")
    id_number_plain = models.CharField(max_length=64, blank=True, verbose_name="证件号")
    business_license = models.CharField(max_length=256, verbose_name="营业执照号(加密)")
    business_scope = models.TextField(blank=True, verbose_name="经营范围")
    registered_capital = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True, verbose_name="注册资本"
    )
    established_date = models.DateField(null=True, blank=True, verbose_name="成立日期")
    registered_address = models.CharField(max_length=256, blank=True, verbose_name="注册地址")
    kyc_status = models.CharField(
        max_length=16, choices=KycStatus.choices, default=KycStatus.PENDING, verbose_name="KYC状态"
    )
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name="提交时间")
    reviewed_by = models.CharField(max_length=64, blank=True, verbose_name="审核人")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="审核时间")
    review_comment = models.CharField(max_length=256, blank=True, verbose_name="审核意见")

    class Meta:
        db_table = "agent_kyc"
        verbose_name = "代理KYC"
        verbose_name_plural = verbose_name

    def submit(self, operator: str = ""):
        """提交尽调资料，进入已提交状态。"""
        self.kyc_status = self.KycStatus.SUBMITTED
        self.submitted_at = timezone.now()
        self.save(update_fields=["kyc_status", "submitted_at", "updated_at"])

    def approve(self, reviewer: str, comment: str = ""):
        """审核通过。"""
        self.kyc_status = self.KycStatus.APPROVED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_comment = comment
        self.save(update_fields=["kyc_status", "reviewed_by", "reviewed_at", "review_comment", "updated_at"])

    def reject(self, reviewer: str, comment: str = ""):
        """审核驳回。"""
        self.kyc_status = self.KycStatus.REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_comment = comment
        self.save(update_fields=["kyc_status", "reviewed_by", "reviewed_at", "review_comment", "updated_at"])
