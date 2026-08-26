"""商户管理模块 — 模型定义。"""
import random
import uuid
from datetime import date, datetime
from django.db import models
from dateutil.relativedelta import relativedelta
from apps.core.models import BaseModel


class Merchant(BaseModel):
    """商户主表。

    记录商户基本信息，关联 KYC、手续费、结算账户等子表。
    """

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "正常"
        SUSPENDED = "SUSPENDED", "暂停"
        CLOSED = "CLOSED", "已关闭"
        PENDING = "PENDING", "待处理"

    merchant_no = models.CharField(max_length=32, unique=True, db_index=True, verbose_name="商户编号")
    merchant_name = models.CharField(max_length=128, verbose_name="商户名称")
    short_name = models.CharField(max_length=64, blank=True, verbose_name="商户简称")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, verbose_name="状态"
    )
    contact_name = models.CharField(max_length=64, blank=True, verbose_name="联系人")
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name="联系电话")
    contact_email = models.EmailField(blank=True, verbose_name="联系邮箱")
    api_key = models.CharField(max_length=64, unique=True, blank=True, verbose_name="API Key")
    api_secret = models.CharField(max_length=256, blank=True, verbose_name="API 密钥(加密)")
    legal_person_name = models.CharField(max_length=64, blank=True, verbose_name="法人姓名")
    license_expiry_date = models.DateField(null=True, blank=True, verbose_name="证照到期日")
    risk_level = models.CharField(max_length=16, default="MEDIUM", verbose_name="风险等级")  # choices: LOW, MEDIUM, HIGH, BLOCKED
    fee_rate = models.DecimalField(max_digits=8, decimal_places=6, default=0, verbose_name="手续费率")
    fixed_fee = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name="固定手续费")
    max_single_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, verbose_name="单笔限额")
    daily_count = models.IntegerField(null=True, blank=True, verbose_name="每日笔数")
    daily_limit = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, verbose_name="日限额")
    next_review_date = models.DateField(null=True, blank=True, verbose_name="下次审核日")
    sanction_status = models.CharField(max_length=16, default="UN", verbose_name="制裁名单")  # choices: UN, OFAC, EU, HMT
    days_to_expiry = models.IntegerField(null=True, blank=True, verbose_name="距到期天数")
    agent = models.ForeignKey(
        "agent.Agent", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="direct_merchants", verbose_name="所属代理商"
    )

    class Meta:
        db_table = "merchant"
        verbose_name = "商户"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        """自动生成商户编号、API Key 和复审日期。"""
        if not self.merchant_no:
            now = datetime.now()
            self.merchant_no = f"M{now.strftime('%Y%m%d%H%M%S')}{random.randint(100000, 999999)}"
        if not self.api_key:
            self.api_key = f"ak_{uuid.uuid4().hex[:32]}"
        # 若未设置复审日期，按风险等级自动计算
        if not self.next_review_date and self.risk_level:
            review_months = {"LOW": 12, "MEDIUM": 6, "HIGH": 3, "BLOCKED": 1}
            months = review_months.get(self.risk_level, 6)
            self.next_review_date = date.today() + relativedelta(months=months)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.merchant_name}({self.merchant_no})"

    @property
    def days_to_expiry_calc(self):
        """计算从今天到证照到期日的天数。"""
        if self.license_expiry_date:
            return (self.license_expiry_date - date.today()).days
        return None


class MerchantKYC(BaseModel):
    """商户 KYC 信息 — 敏感字段加密存储。"""

    merchant = models.OneToOneField(
        Merchant, on_delete=models.CASCADE, related_name="kyc", verbose_name="商户"
    )
    legal_person = models.CharField(max_length=64, verbose_name="法人姓名")
    id_number = models.CharField(max_length=256, verbose_name="身份证号(加密)")
    business_license = models.CharField(max_length=256, verbose_name="营业执照号(加密)")
    business_scope = models.TextField(blank=True, verbose_name="经营范围")
    registered_capital = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, verbose_name="注册资本"
    )
    established_date = models.DateField(null=True, verbose_name="成立日期")
    registered_address = models.CharField(max_length=256, blank=True, verbose_name="注册地址")
    id_type = models.CharField(max_length=16, default="ID_CARD", verbose_name="证件类型")  # choices: ID_CARD, PASSPORT, BUSINESS_LICENSE
    id_number_plain = models.CharField(max_length=64, blank=True, verbose_name="证件号码")
    nationality = models.CharField(max_length=64, blank=True, verbose_name="国籍")
    kyc_status = models.CharField(max_length=16, default="PENDING", verbose_name="KYC状态")  # choices: PENDING, APPROVED, REJECTED, WARNING
    remark = models.TextField(blank=True, verbose_name="审核备注")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="审核时间")

    class Meta:
        db_table = "merchant_kyc"
        verbose_name = "商户KYC"
        verbose_name_plural = verbose_name


class MerchantFee(BaseModel):
    """商户手续费配置 — 支持按产品类型的多费率模型。"""

    class FeeModel(models.TextChoices):
        FIXED = "FIXED", "固定金额"
        PERCENTAGE = "PERCENTAGE", "按比例"
        TIERED = "TIERED", "阶梯费率"

    class ProductType(models.TextChoices):
        ONLINE_BANK = "ONLINE_BANK", "银行网银支付"
        AUTHORIZED = "AUTHORIZED", "授权支付"
        WIRE_TRANSFER = "WIRE_TRANSFER", "转款汇款"

    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="fees", verbose_name="商户"
    )
    product_type = models.CharField(
        max_length=32, choices=ProductType.choices, verbose_name="支付产品"
    )
    fee_model = models.CharField(
        max_length=16, choices=FeeModel.choices, verbose_name="费率模型"
    )
    fixed_fee = models.DecimalField(
        max_digits=12, decimal_places=4, default=0, verbose_name="固定手续费"
    )
    fee_rate = models.DecimalField(
        max_digits=8, decimal_places=6, default=0, verbose_name="手续费比例"
    )
    min_fee = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="最低手续费"
    )
    max_fee = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="最高手续费"
    )
    effective_from = models.DateField(verbose_name="生效日期")
    effective_to = models.DateField(null=True, blank=True, verbose_name="失效日期")

    class Meta:
        db_table = "merchant_fee"
        verbose_name = "商户手续费"
        verbose_name_plural = verbose_name
        ordering = ["-effective_from"]


class MerchantSettlementAccount(BaseModel):
    """商户结算账户 — 资金清算时打入的账户。"""

    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="settlement_accounts", verbose_name="商户"
    )
    bank_name = models.CharField(max_length=128, verbose_name="银行名称")
    bank_branch = models.CharField(max_length=128, blank=True, verbose_name="支行")
    account_name = models.CharField(max_length=128, verbose_name="账户名")
    account_number = models.CharField(max_length=256, verbose_name="账号(加密)")
    account_type = models.CharField(max_length=16, default="CORPORATE", verbose_name="账户类型")
    is_default = models.BooleanField(default=False, verbose_name="默认账户")

    class Meta:
        db_table = "merchant_settlement_account"
        verbose_name = "商户结算账户"
        verbose_name_plural = verbose_name

    def save(self, *args, **kwargs):
        """确保只有一个默认账户。"""
        if self.is_default:
            MerchantSettlementAccount.objects.filter(
                merchant=self.merchant, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class MerchantPaymentProduct(BaseModel):
    """商户支付产品配置 — 控制商户可使用的支付方式。"""

    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="payment_products", verbose_name="商户"
    )
    product_type = models.CharField(max_length=32, verbose_name="产品类型")
    is_enabled = models.BooleanField(default=True, verbose_name="是否启用")
    max_single_amount = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, verbose_name="单笔限额"
    )
    daily_limit = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, verbose_name="日限额"
    )

    class Meta:
        db_table = "merchant_payment_product"
        unique_together = [["merchant", "product_type"]]
        verbose_name = "商户支付产品"
        verbose_name_plural = verbose_name
