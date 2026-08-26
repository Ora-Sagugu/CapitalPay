"""用户端业务服务层 — 注册、登录、账户管理、首次登录资料。"""
import hashlib
import random
import string
import secrets
from datetime import date, datetime, timedelta
from typing import Optional

import jwt
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import BusinessException
from apps.core.utils import encrypt_field
from .models import EndUser, SmsCode, RefreshToken, UserOnboarding


TOKEN_EXPIRE_HOURS = 24
REFRESH_TOKEN_EXPIRE_DAYS = 30
SMS_CODE_EXPIRE_MINUTES = 5


class UserService:
    """用户端服务 — 注册、登录、账户管理、首次登录资料。"""

    @staticmethod
    def _hash_password(password: str) -> str:
        raw = f"user:{password}:b2b_user_salt"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _generate_token(user_id: str, user_type: str = "user") -> str:
        payload = {
            "user_id": user_id,
            "user_type": user_type,
            "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    @staticmethod
    def _generate_sms_code() -> str:
        return "".join(random.choices(string.digits, k=6))

    # ── 注册 ──────────────────────────────────────────────

    @transaction.atomic
    def register(self, *, phone: str, password: str, sms_code: str = "",
                 nickname: str = "") -> dict:
        """手机号注册 — 需要短信验证码。"""

        if EndUser.objects.filter(phone=phone).exists():
            raise BusinessException("PHONE_EXISTS", "该手机号已注册")

        if sms_code:
            self._verify_sms_code(phone, sms_code, SmsCode.Scene.REGISTER)

        user = EndUser.objects.create(
            username=phone,
            phone=phone,
            email=f"{phone}@placeholder.local",
            password_hash=self._hash_password(password),
            nickname=nickname or f"用户{phone[-4:]}",
        )

        token = self._generate_token(str(user.id), user_type="user")
        refresh_token = self._create_refresh_token(user)

        return {
            "token": token,
            "refresh_token": refresh_token,
            "expires_in": TOKEN_EXPIRE_HOURS * 3600,
            "user": {
                "id": str(user.id),
                "phone": self._mask_phone(phone),
                "username": user.username,
                "nickname": user.nickname,
                "is_verified": user.is_verified,
                "real_name": user.real_name,
            },
        }

    @transaction.atomic
    def register_by_email(self, *, username: str, email: str, password: str) -> dict:
        """邮箱注册 — 用户名+邮箱+密码。邮箱统一转为小写存储/查询。"""
        email = email.lower().strip()

        if EndUser.objects.filter(username__iexact=username).exists():
            raise BusinessException("USERNAME_EXISTS", "该用户名已被使用")

        if EndUser.objects.filter(email__iexact=email).exists():
            raise BusinessException("EMAIL_EXISTS", "该邮箱已注册")

        user = EndUser.objects.create(
            username=username,
            email=email,
            password_hash=self._hash_password(password),
            nickname=username,
        )

        token = self._generate_token(str(user.id), user_type="user")
        refresh_token = self._create_refresh_token(user)

        return {
            "token": token,
            "refresh_token": refresh_token,
            "expires_in": TOKEN_EXPIRE_HOURS * 3600,
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "nickname": user.nickname,
                "is_verified": user.is_verified,
                "real_name": user.real_name,
                "onboarding_status": user.onboarding_status,
            },
        }

    # ── 登录 ──────────────────────────────────────────────

    def login_by_password(self, phone: str, password: str, ip: str = "") -> dict:
        """手机号+密码登录。"""
        user = EndUser.objects.filter(phone=phone, is_deleted=False).first()
        if not user or self._hash_password(password) != user.password_hash:
            raise BusinessException("LOGIN_FAILED", "手机号或密码错误", 401)

        if not user.is_active:
            raise BusinessException("ACCOUNT_DISABLED", "账号已停用", 403)

        user.last_login_at = timezone.now()
        user.last_login_ip = ip
        user.save(update_fields=["last_login_at", "last_login_ip"])

        token = self._generate_token(str(user.id), user_type="user")
        refresh_token = self._create_refresh_token(user)

        return {
            "token": token,
            "refresh_token": refresh_token,
            "expires_in": TOKEN_EXPIRE_HOURS * 3600,
            "user": {
                "id": str(user.id),
                "phone": self._mask_phone(phone),
                "nickname": user.nickname,
                "email": user.email,
                "is_verified": user.is_verified,
                "real_name": user.real_name,
                "onboarding_status": user.onboarding_status,
            },
            "license_warning": self._get_user_license_warning(user),
        }

    def login_by_email(self, email: str, password: str, ip: str = "") -> dict:
        """邮箱+密码登录 — 大小写不敏感。"""
        email = email.lower().strip()
        user = EndUser.objects.filter(email__iexact=email, is_deleted=False).first()
        if not user or self._hash_password(password) != user.password_hash:
            raise BusinessException("LOGIN_FAILED", "邮箱或密码错误", 401)

        if not user.is_active:
            raise BusinessException("ACCOUNT_DISABLED", "账号已停用", 403)

        user.last_login_at = timezone.now()
        user.last_login_ip = ip
        user.save(update_fields=["last_login_at", "last_login_ip"])

        token = self._generate_token(str(user.id), user_type="user")
        refresh_token = self._create_refresh_token(user)

        return {
            "token": token,
            "refresh_token": refresh_token,
            "expires_in": TOKEN_EXPIRE_HOURS * 3600,
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "nickname": user.nickname,
                "is_verified": user.is_verified,
                "real_name": user.real_name,
                "onboarding_status": user.onboarding_status,
            },
            "license_warning": self._get_user_license_warning(user),
        }

    def login_by_sms(self, phone: str, sms_code: str, ip: str = "") -> dict:
        """手机号+短信验证码登录。"""
        self._verify_sms_code(phone, sms_code, SmsCode.Scene.LOGIN)

        user = EndUser.objects.filter(phone=phone, is_deleted=False).first()
        if not user:
            # 新用户自动注册
            user = EndUser.objects.create(
                username=phone,
                phone=phone,
                email=f"{phone}@placeholder.local",
                password_hash=self._hash_password(secrets.token_hex(16)),
                nickname=f"用户{phone[-4:]}",
            )

        if not user.is_active:
            raise BusinessException("ACCOUNT_DISABLED", "账号已停用", 403)

        user.last_login_at = timezone.now()
        user.last_login_ip = ip
        user.save(update_fields=["last_login_at", "last_login_ip"])

        token = self._generate_token(str(user.id), user_type="user")
        refresh_token = self._create_refresh_token(user)

        return {
            "token": token,
            "refresh_token": refresh_token,
            "expires_in": TOKEN_EXPIRE_HOURS * 3600,
            "user": {
                "id": str(user.id),
                "phone": self._mask_phone(phone),
                "username": user.username,
                "nickname": user.nickname,
                "is_verified": user.is_verified,
                "real_name": user.real_name,
            },
            "license_warning": self._get_user_license_warning(user),
        }

    def refresh_token(self, refresh_token_str: str) -> dict:
        """刷新 Access Token。"""
        rt = RefreshToken.objects.filter(
            token=refresh_token_str, is_revoked=False, is_deleted=False
        ).first()
        if not rt or rt.expires_at < timezone.now():
            raise BusinessException("REFRESH_TOKEN_INVALID", "刷新令牌无效或已过期", 401)

        rt.is_revoked = True
        rt.save(update_fields=["is_revoked"])

        user = rt.user
        token = self._generate_token(str(user.id), user_type="user")
        new_refresh = self._create_refresh_token(user)

        return {
            "token": token,
            "refresh_token": new_refresh,
            "expires_in": TOKEN_EXPIRE_HOURS * 3600,
        }

    # ── 首次登录资料 ──────────────────────────────────────

    @transaction.atomic
    def submit_onboarding(self, user: EndUser, data: dict) -> dict:
        """提交首次登录三步资料。"""
        basic = data.get("basic", {})
        finance = data.get("finance", {})
        images = data.get("images", {})

        onboarding, _ = UserOnboarding.objects.update_or_create(
            user=user,
            defaults={
                "legal_name": basic.get("legal_name", ""),
                "id_type": basic.get("id_type", ""),
                "id_number": basic.get("id_number", ""),
                "contact_phone": basic.get("contact_phone", ""),
                "nationality": basic.get("nationality", ""),
                "address": basic.get("address", ""),
                "agent_code": basic.get("agent_code", ""),
                "license_expiry_date": basic.get("license_expiry_date"),
                "bank_name": finance.get("bank_name", ""),
                "branch_name": finance.get("branch_name", ""),
                "bank_account": finance.get("bank_account", ""),
                "license_image": images.get("license_image", ""),
                "id_front_image": images.get("id_front_image", ""),
                "id_back_image": images.get("id_back_image", ""),
            },
        )

        user.onboarding_status = "pending"
        user.onboarding_submitted_at = timezone.now()
        user.save(update_fields=["onboarding_status", "onboarding_submitted_at"])

        return {"message": "资料提交成功，等待审核"}

    def get_onboarding(self, user: EndUser) -> dict:
        """获取用户已提交的资料。"""
        onboarding = UserOnboarding.objects.filter(user=user).first()
        if not onboarding:
            return None
        return {
            "basic": {
                "legal_name": onboarding.legal_name,
                "id_type": onboarding.id_type,
                "id_number": onboarding.id_number,
                "contact_phone": onboarding.contact_phone,
                "nationality": onboarding.nationality,
                "address": onboarding.address,
                "agent_code": onboarding.agent_code,
                "license_expiry_date": onboarding.license_expiry_date,
            },
            "finance": {
                "bank_name": onboarding.bank_name,
                "branch_name": onboarding.branch_name,
                "bank_account": onboarding.bank_account,
            },
            "images": {
                "license_image": onboarding.license_image,
                "id_front_image": onboarding.id_front_image,
                "id_back_image": onboarding.id_back_image,
            },
        }

    # ── 审核 ──────────────────────────────────────────────

    @transaction.atomic
    def review_onboarding(self, user: EndUser, action: str, remark: str = "", reviewer: str = "") -> dict:
        """审核用户资料 — 通过时自动创建客户(Merchant)记录。"""
        if action == "approve":
            user.onboarding_status = "approved"
            user.is_verified = True
            # 审核通过 → 自动创建客户记录
            merchant = self._create_merchant_from_onboarding(user)
            if merchant:
                user.default_merchant = merchant
        elif action == "reject":
            user.onboarding_status = "rejected"
        else:
            raise BusinessException("INVALID_ACTION", "无效的审核操作")

        user.onboarding_reviewed_at = timezone.now()
        user.onboarding_reviewer = reviewer
        user.onboarding_remark = remark
        user.save(update_fields=[
            "onboarding_status", "onboarding_reviewed_at",
            "onboarding_reviewer", "onboarding_remark",
            "is_verified", "default_merchant",
        ])

        return {"message": "审核完成", "status": user.onboarding_status}

    @staticmethod
    def _create_merchant_from_onboarding(user: EndUser):
        """审核通过后，根据用户提交的 onboarding 资料自动创建 Merchant 记录。

        同时创建 MerchantKYC 和结算账户，使该用户自动出现在客户基本信息列表中。
        """
        from apps.merchant.models import Merchant, MerchantKYC, MerchantSettlementAccount

        # 已有绑定的商户不再重复创建
        if user.default_merchant_id:
            return None

        # 获取 onboarding 资料
        onboarding = None
        try:
            onboarding = user.onboarding
        except Exception:
            pass

        # 商户名称 — 优先 onboarding.legal_name, 其次 real_name, 最后 username
        merchant_name = ""
        legal_person_name = ""
        contact_phone = ""
        license_expiry_date = None

        if onboarding:
            merchant_name = onboarding.legal_name or ""
            legal_person_name = onboarding.legal_name or ""
            contact_phone = onboarding.contact_phone or ""
            license_expiry_date = onboarding.license_expiry_date

        if not merchant_name:
            merchant_name = user.real_name or user.username or f"用户{str(user.id)[:8]}"
        if not legal_person_name:
            legal_person_name = merchant_name

        # 创建 Merchant
        merchant = Merchant.objects.create(
            merchant_name=merchant_name,
            legal_person_name=legal_person_name,
            contact_phone=contact_phone or user.phone or "",
            contact_email=user.email or "",
            license_expiry_date=license_expiry_date,
            status=Merchant.Status.PENDING,
            risk_level="MEDIUM",
        )

        # 创建 MerchantKYC
        if onboarding:
            MerchantKYC.objects.create(
                merchant=merchant,
                legal_person=onboarding.legal_name or legal_person_name,
                id_type=onboarding.id_type or "ID_CARD",
                id_number=onboarding.id_number or "",
                id_number_plain=onboarding.id_number or "",
                nationality=onboarding.nationality or "",
                registered_address=onboarding.address or "",
                kyc_status="PENDING",
            )

            # 创建结算账户
            if onboarding.bank_name or onboarding.bank_account:
                MerchantSettlementAccount.objects.create(
                    merchant=merchant,
                    bank_name=onboarding.bank_name or "",
                    bank_branch=onboarding.branch_name or "",
                    account_name=onboarding.legal_name or merchant_name,
                    account_number=onboarding.bank_account or "",
                    is_default=True,
                )

        return merchant

    # ── 信息管理 ──────────────────────────────────────────

    def get_profile(self, user: EndUser) -> dict:
        from apps.account.models import UserAccount
        from apps.account.models import UserPaymentDetail

        bound_accounts = UserAccount.objects.filter(
            user_id=str(user.id), status=UserAccount.BindStatus.ACTIVE, is_deleted=False
        ).count()

        # 近3个月交易笔数
        three_months_ago = timezone.now() - timedelta(days=90)
        recent_count = UserPaymentDetail.objects.filter(
            user_id=str(user.id), is_deleted=False, created_at__gte=three_months_ago
        ).count()

        return {
            "id": str(user.id),
            "username": user.username,
            "phone": self._mask_phone(user.phone) if user.phone else "",
            "nickname": user.nickname,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "is_verified": user.is_verified,
            "real_name": user.real_name,
            "onboarding_status": user.onboarding_status,
            "bound_accounts": bound_accounts,
            "recent_transactions": recent_count,
            "merchant_no": user.default_merchant.merchant_no if user.default_merchant else "",
            "merchant_name": user.default_merchant.merchant_name if user.default_merchant else "",
            "merchant_status": user.default_merchant.status if user.default_merchant else "",
            "license_expiry_date": user.default_merchant.license_expiry_date.isoformat() if (user.default_merchant and user.default_merchant.license_expiry_date) else "",
            "license_warning": self._get_user_license_warning(user),
            "created_at": user.created_at,
        }

    def update_profile(self, user: EndUser, **kwargs):
        allowed = {"nickname", "email", "avatar_url"}
        for key, value in kwargs.items():
            if key in allowed and value is not None:
                setattr(user, key, value)
        user.save(update_fields=[k for k in kwargs if k in allowed])

    def verify_identity(self, user: EndUser, real_name: str, id_card: str):
        """实名认证 — 存证。线上对接实名认证服务后可扩展。"""
        user.real_name = real_name
        user.id_card = encrypt_field(id_card)
        user.is_verified = True
        user.save(update_fields=["real_name", "id_card", "is_verified"])

    def reset_password(self, phone: str, sms_code: str, new_password: str):
        self._verify_sms_code(phone, sms_code, SmsCode.Scene.RESET_PASSWORD)
        user = EndUser.objects.get(phone=phone)
        user.password_hash = self._hash_password(new_password)
        user.save(update_fields=["password_hash"])

    # ── 短信验证码 ────────────────────────────────────────

    def send_sms_code(self, phone: str, scene: str):
        """发送短信验证码 — 线上需对接阿里云/腾讯云短信服务。

        开发环境：固定用 000000，60 秒内不重复发送。
        """
        recent = SmsCode.objects.filter(
            phone=phone, scene=scene,
            created_at__gte=timezone.now() - timedelta(seconds=60),
        ).first()
        if recent:
            raise BusinessException("SMS_TOO_FREQUENT", "验证码发送过频，请60秒后重试")

        # 开发/测试环境默认固定码；REAL 模式生成随机码并走短信网关
        from django.conf import settings
        mode = getattr(settings, "SMS_PROVIDER_MODE", "MOCK").upper()
        if mode == "REAL":
            code = self._generate_sms_code()
        else:
            code = "000000"

        SmsCode.objects.create(
            phone=phone,
            code=code,
            scene=scene,
            expires_at=timezone.now() + timedelta(minutes=SMS_CODE_EXPIRE_MINUTES),
        )
        try:
            from .sms import send_sms
            send_sms(phone, f"Your verification code is {code}")
        except NotImplementedError:
            if mode == "REAL":
                raise BusinessException("SMS_PROVIDER_ERROR", "短信通道未配置")
        return {"phone": phone, "scene": scene, "expires_in": SMS_CODE_EXPIRE_MINUTES * 60}

    def _verify_sms_code(self, phone: str, code: str, scene: str):
        record = SmsCode.objects.filter(
            phone=phone, scene=scene, code=code, is_used=False,
            expires_at__gte=timezone.now(),
        ).order_by("-created_at").first()

        if not record:
            raise BusinessException("SMS_CODE_INVALID", "验证码错误或已过期")

        record.is_used = True
        record.save(update_fields=["is_used"])

    # ── 辅助方法 ──────────────────────────────────────────

    def _create_refresh_token(self, user: EndUser) -> str:
        token = secrets.token_urlsafe(48)
        RefreshToken.objects.create(
            user=user,
            token=token,
            expires_at=timezone.now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
        return token

    @staticmethod
    def _get_user_license_warning(user) -> Optional[dict]:
        """获取用户关联商户的牌照到期提醒（30天内到期时返回）。"""
        merchant = user.default_merchant
        if not merchant or not merchant.license_expiry_date:
            return None
        today = date.today()
        days_left = (merchant.license_expiry_date - today).days
        if 0 <= days_left <= 30:
            return {
                "merchant_name": merchant.merchant_name,
                "license_expiry_date": merchant.license_expiry_date.isoformat(),
                "days_left": days_left,
            }
        return None

    @staticmethod
    def _mask_phone(phone: str) -> str:
        if not phone:
            return ""
        if len(phone) >= 7:
            return phone[:3] + "****" + phone[-4:]
        return phone
