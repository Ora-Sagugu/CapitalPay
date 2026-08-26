"""用户端模型 — 终端用户账号、短信验证码、登录凭证、首次登录资料。

包含: EndUser（C端用户）、SmsCode（短信验证码）、RefreshToken（刷新令牌）、UserOnboarding（首次登录资料）。
"""
from django.db import models
from apps.core.models import BaseModel


class EndUser(BaseModel):
    """终端用户 — B2B 支付平台面向的付款方（C端用户）。

    用户可以通过邮箱/手机号注册，绑定银行账户，发起支付。
    """
    username = models.CharField(max_length=64, unique=True, default="", verbose_name="用户名")
    password_hash = models.CharField(max_length=256, verbose_name="密码哈希")
    email = models.EmailField(unique=True, default="", verbose_name="邮箱")
    phone = models.CharField(max_length=20, null=True, blank=True, unique=True, verbose_name="手机号")
    nickname = models.CharField(max_length=64, blank=True, verbose_name="昵称")
    avatar_url = models.CharField(max_length=512, blank=True, verbose_name="头像URL")
    is_active = models.BooleanField(default=True, verbose_name="启用")
    is_verified = models.BooleanField(default=False, verbose_name="实名认证")
    real_name = models.CharField(max_length=64, blank=True, verbose_name="真实姓名")
    id_card = models.CharField(max_length=256, blank=True, verbose_name="身份证号(加密)")
    last_login_at = models.DateTimeField(null=True, blank=True, verbose_name="最后登录时间")
    last_login_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="最后登录IP")

    # 首次登录资料与审核状态
    onboarding_status = models.CharField(
        max_length=16,
        choices=[("none", "未填写"), ("pending", "审核中"), ("approved", "已通过"), ("rejected", "已拒绝")],
        default="none",
        verbose_name="资料审核状态",
    )
    onboarding_submitted_at = models.DateTimeField(null=True, blank=True, verbose_name="资料提交时间")
    onboarding_reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="资料审核时间")
    onboarding_reviewer = models.CharField(max_length=64, blank=True, verbose_name="审核人")
    onboarding_remark = models.CharField(max_length=512, blank=True, verbose_name="审核备注")

    default_merchant = models.ForeignKey(
        "merchant.Merchant", on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="默认商户"
    )

    class Meta:
        db_table = "end_user"
        verbose_name = "终端用户"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.nickname or self.username}"


class UserOnboarding(BaseModel):
    """用户首次登录资料 — 三步向导提交的企业/个人信息。"""

    class IdType(models.TextChoices):
        ID_CARD = "id_card", "身份证"
        PASSPORT = "passport", "护照"
        BUSINESS_LICENSE = "business_license", "营业执照"
        OTHER = "other", "其他"

    user = models.OneToOneField(
        EndUser, on_delete=models.CASCADE, related_name="onboarding", verbose_name="用户"
    )

    # ── 第一步：基本信息 ──
    legal_name = models.CharField(max_length=128, blank=True, verbose_name="法人姓名")
    id_type = models.CharField(
        max_length=32, choices=IdType.choices, blank=True, verbose_name="证件类型"
    )
    id_number = models.CharField(max_length=128, blank=True, verbose_name="证件号码")
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name="手机号码")
    nationality = models.CharField(max_length=64, blank=True, verbose_name="国籍")
    address = models.CharField(max_length=512, blank=True, verbose_name="地址")
    agent_code = models.CharField(max_length=64, blank=True, verbose_name="代理编码")
    license_expiry_date = models.DateField(null=True, blank=True, verbose_name="证照到期日")

    # ── 第二步：财务信息 ──
    bank_name = models.CharField(max_length=256, blank=True, verbose_name="开户银行")
    branch_name = models.CharField(max_length=256, blank=True, verbose_name="支行名称")
    bank_account = models.CharField(max_length=128, blank=True, verbose_name="银行账号")

    # ── 第三步：上传图片 ──
    license_image = models.TextField(blank=True, verbose_name="营业执照图片")
    id_front_image = models.TextField(blank=True, verbose_name="法人证件正面")
    id_back_image = models.TextField(blank=True, verbose_name="法人证件背面")

    class Meta:
        db_table = "user_onboarding"
        verbose_name = "用户资料"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]


class SmsCode(models.Model):
    """短信验证码 — 用于用户注册、登录、找回密码。"""

    class Scene(models.TextChoices):
        REGISTER = "REGISTER", "注册"
        LOGIN = "LOGIN", "登录"
        RESET_PASSWORD = "RESET_PASSWORD", "重置密码"
        BIND_ACCOUNT = "BIND_ACCOUNT", "绑定账户"

    phone = models.CharField(max_length=20, verbose_name="手机号")
    code = models.CharField(max_length=6, verbose_name="验证码")
    scene = models.CharField(max_length=32, choices=Scene.choices, verbose_name="场景")
    is_used = models.BooleanField(default=False, verbose_name="已使用")
    expires_at = models.DateTimeField(verbose_name="过期时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "sms_code"
        verbose_name = "短信验证码"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["phone", "scene", "created_at"]),
        ]


class RefreshToken(BaseModel):
    """刷新令牌 — 长生命周期的 Token，用于获取新的短时 Access Token。"""

    user = models.ForeignKey(
        EndUser, on_delete=models.CASCADE, verbose_name="用户"
    )
    token = models.CharField(max_length=256, unique=True, verbose_name="刷新令牌")
    expires_at = models.DateTimeField(verbose_name="过期时间")
    is_revoked = models.BooleanField(default=False, verbose_name="已撤销")

    class Meta:
        db_table = "user_refresh_token"
        verbose_name = "刷新令牌"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
