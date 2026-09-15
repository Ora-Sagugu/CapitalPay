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

    @staticmethod
    def ensure_portal_role(user: EndUser) -> EndUser:
        """Legacy accounts that already started customer onboarding stay customers."""
        role = user.portal_role or "none"
        if role != "none":
            return user
        if user.default_merchant_id or (user.onboarding_status and user.onboarding_status != "none"):
            user.portal_role = "customer"
            user.save(update_fields=["portal_role"])
        return user

    def _session_user(self, user: EndUser) -> dict:
        self.ensure_portal_role(user)
        user.refresh_from_db()
        agent = user.default_agent
        payload = {
            "id": str(user.id),
            "username": user.username,
            "nickname": user.nickname,
            "email": user.email,
            "is_verified": user.is_verified,
            "real_name": user.real_name,
            "onboarding_status": user.onboarding_status,
            "portal_role": user.portal_role or "none",
            "default_agent_id": str(agent.id) if agent else "",
            "agent_no": agent.agent_no if agent else "",
        }
        if user.phone:
            payload["phone"] = self._mask_phone(user.phone)
        return payload

    @transaction.atomic
    def choose_role(self, user: EndUser, role: str) -> dict:
        user = EndUser.objects.select_for_update().get(pk=user.pk)
        self.ensure_portal_role(user)
        user.refresh_from_db()
        if (user.portal_role or "none") != "none":
            raise BusinessException(
                "ROLE_ALREADY_CHOSEN",
                "The account identity has already been selected",
                409,
            )
        if role not in ("customer", "agent"):
            raise BusinessException("INVALID_ROLE", "Identity must be customer or agent")
        user.portal_role = role
        user.save(update_fields=["portal_role"])
        return {"portal_role": role, "user": self._session_user(user)}

    # ── 注册 ──────────────────────────────────────────────

    def _assign_portal_role(self, user: EndUser, portal_role: str = "") -> EndUser:
        if not portal_role:
            return user
        if portal_role not in ("customer", "agent"):
            raise BusinessException("INVALID_ROLE", "Identity must be customer or agent")
        user.portal_role = portal_role
        user.save(update_fields=["portal_role"])
        return user

    def _bind_or_assert_portal(self, user: EndUser, portal_role: str = "") -> EndUser:
        """Lock identity on first login, or reject the wrong portal."""
        if not portal_role:
            return user
        if portal_role not in ("customer", "agent"):
            raise BusinessException("INVALID_ROLE", "Identity must be customer or agent")
        current = user.portal_role or "none"
        if current in ("", "none"):
            return self._assign_portal_role(user, portal_role)
        if current != portal_role:
            if current == "agent":
                message = "This account is an Agent. Sign in at the Agent portal (/agent/login)."
            else:
                message = "This account is a Customer. Sign in at the Customer portal (/login)."
            raise BusinessException("WRONG_PORTAL", message, 403)
        return user

    @transaction.atomic
    def register(self, *, phone: str, password: str, sms_code: str = "",
                 nickname: str = "", portal_role: str = "") -> dict:
        """手机号注册 — 需要短信验证码。可同时选定 Agent 或 Customer 身份。"""

        if EndUser.objects.filter(phone=phone).exists():
            raise BusinessException("PHONE_EXISTS", "This mobile number has already been registered")

        if sms_code:
            self._verify_sms_code(phone, sms_code, SmsCode.Scene.REGISTER)

        user = EndUser.objects.create(
            username=phone,
            phone=phone,
            email=f"{phone}@placeholder.local",
            password_hash=self._hash_password(password),
            nickname=nickname or f"用户{phone[-4:]}",
        )
        self._assign_portal_role(user, portal_role)

        token = self._generate_token(str(user.id), user_type="user")
        refresh_token = self._create_refresh_token(user)

        return {
            "token": token,
            "refresh_token": refresh_token,
            "expires_in": TOKEN_EXPIRE_HOURS * 3600,
            "user": self._session_user(user),
        }

    @staticmethod
    def _require_gmail(email: str) -> str:
        email = (email or "").lower().strip()
        if not email.endswith("@gmail.com") or email.count("@") != 1 or email.startswith("@"):
            raise BusinessException("EMAIL_DOMAIN", "Only @gmail.com email addresses are allowed")
        return email

    @transaction.atomic
    def register_by_email(self, *, username: str, email: str, password: str,
                          portal_role: str = "") -> dict:
        """邮箱注册 — 用户名+邮箱+密码。仅允许 @gmail.com；邮箱统一小写存储/查询。"""
        email = self._require_gmail(email)
        username = (username or "").strip() or email.split("@", 1)[0]

        if EndUser.objects.filter(username__iexact=username).exists():
            raise BusinessException("USERNAME_EXISTS", "This username is already in use")

        if EndUser.objects.filter(email__iexact=email).exists():
            raise BusinessException("EMAIL_EXISTS", "This email address has already been registered")

        user = EndUser.objects.create(
            username=username,
            email=email,
            password_hash=self._hash_password(password),
            nickname=username,
        )
        self._assign_portal_role(user, portal_role)

        token = self._generate_token(str(user.id), user_type="user")
        refresh_token = self._create_refresh_token(user)

        return {
            "token": token,
            "refresh_token": refresh_token,
            "expires_in": TOKEN_EXPIRE_HOURS * 3600,
            "user": self._session_user(user),
        }

    # ── 登录 ──────────────────────────────────────────────

    def login_by_password(self, phone: str, password: str, ip: str = "",
                          portal_role: str = "") -> dict:
        """手机号+密码登录。"""
        user = EndUser.objects.filter(phone=phone, is_deleted=False).first()
        if not user or self._hash_password(password) != user.password_hash:
            raise BusinessException("LOGIN_FAILED", "The mobile number or password is incorrect", 401)

        if not user.is_active:
            raise BusinessException("ACCOUNT_DISABLED", "The account has been disabled", 403)

        self._bind_or_assert_portal(user, portal_role)
        user.refresh_from_db()

        user.last_login_at = timezone.now()
        user.last_login_ip = ip
        user.save(update_fields=["last_login_at", "last_login_ip"])

        token = self._generate_token(str(user.id), user_type="user")
        refresh_token = self._create_refresh_token(user)

        return {
            "token": token,
            "refresh_token": refresh_token,
            "expires_in": TOKEN_EXPIRE_HOURS * 3600,
            "user": self._session_user(user),
            "license_warning": self._get_user_license_warning(user),
        }

    def login_by_email(self, email: str, password: str, ip: str = "",
                       portal_role: str = "") -> dict:
        """邮箱+密码登录 — 仅 @gmail.com，大小写不敏感。"""
        email = self._require_gmail(email)
        user = EndUser.objects.filter(email__iexact=email, is_deleted=False).first()
        if not user or self._hash_password(password) != user.password_hash:
            raise BusinessException("LOGIN_FAILED", "The email address or password is incorrect", 401)

        if not user.is_active:
            raise BusinessException("ACCOUNT_DISABLED", "The account has been disabled", 403)

        self._bind_or_assert_portal(user, portal_role)
        user.refresh_from_db()

        user.last_login_at = timezone.now()
        user.last_login_ip = ip
        user.save(update_fields=["last_login_at", "last_login_ip"])

        token = self._generate_token(str(user.id), user_type="user")
        refresh_token = self._create_refresh_token(user)

        return {
            "token": token,
            "refresh_token": refresh_token,
            "expires_in": TOKEN_EXPIRE_HOURS * 3600,
            "user": self._session_user(user),
            "license_warning": self._get_user_license_warning(user),
        }

    def login_by_sms(self, phone: str, sms_code: str, ip: str = "",
                     portal_role: str = "") -> dict:
        """手机号+短信验证码登录。"""
        self._verify_sms_code(phone, sms_code, SmsCode.Scene.LOGIN)

        user = EndUser.objects.filter(phone=phone, is_deleted=False).first()
        if not user:
            # 新用户自动注册，身份跟随当前门户地址
            user = EndUser.objects.create(
                username=phone,
                phone=phone,
                email=f"{phone}@placeholder.local",
                password_hash=self._hash_password(secrets.token_hex(16)),
                nickname=f"用户{phone[-4:]}",
            )
            self._assign_portal_role(user, portal_role or "customer")
        else:
            self._bind_or_assert_portal(user, portal_role)
            user.refresh_from_db()

        if not user.is_active:
            raise BusinessException("ACCOUNT_DISABLED", "The account has been disabled", 403)

        user.last_login_at = timezone.now()
        user.last_login_ip = ip
        user.save(update_fields=["last_login_at", "last_login_ip"])

        token = self._generate_token(str(user.id), user_type="user")
        refresh_token = self._create_refresh_token(user)

        return {
            "token": token,
            "refresh_token": refresh_token,
            "expires_in": TOKEN_EXPIRE_HOURS * 3600,
            "user": self._session_user(user),
            "license_warning": self._get_user_license_warning(user),
        }

    def refresh_token(self, refresh_token_str: str) -> dict:
        """刷新 Access Token。"""
        rt = RefreshToken.objects.filter(
            token=refresh_token_str, is_revoked=False, is_deleted=False
        ).first()
        if not rt or rt.expires_at < timezone.now():
            raise BusinessException("REFRESH_TOKEN_INVALID", "The refresh token is invalid or has expired", 401)

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
        """提交首次登录资料（基本信息 + 财务信息 + 证件）。"""
        self.ensure_portal_role(user)
        user.refresh_from_db()
        if (user.portal_role or "none") == "none":
            raise BusinessException(
                "ROLE_REQUIRED",
                "Select Customer or Agent identity before submitting onboarding",
                409,
            )
        basic = data.get("basic", {})
        images = data.get("images", {})
        if user.portal_role == "agent":
            basic = {**basic, "agent_code": ""}
            agent_review_status = UserOnboarding.AgentReviewStatus.NONE
        else:
            agent_code = (basic.get("agent_code") or "").strip()
            basic = {**basic, "agent_code": agent_code}
            self._resolve_agent_by_code(agent_code)
            agent_review_status = (
                UserOnboarding.AgentReviewStatus.PENDING
                if agent_code
                else UserOnboarding.AgentReviewStatus.NONE
            )

        # Bank / settlement details come from onboarding finance (customers).
        finance = data.get("finance", {}) or {}
        onboarding_defaults = {
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
            "account_name": finance.get("account_name", ""),
            "bank_account": finance.get("bank_account", ""),
            "swift_code": finance.get("swift_code", ""),
            "license_image": images.get("license_image", ""),
            "id_front_image": images.get("id_front_image", ""),
            "id_back_image": images.get("id_back_image", ""),
            "agent_review_status": agent_review_status,
            "agent_reviewed_at": None,
            "agent_reviewer": "",
            "agent_remark": "",
        }

        onboarding, _ = UserOnboarding.objects.update_or_create(
            user=user,
            defaults=onboarding_defaults,
        )

        user.onboarding_status = "pending"
        user.onboarding_submitted_at = timezone.now()
        user.save(update_fields=["onboarding_status", "onboarding_submitted_at"])

        return {"message": "The profile has been submitted and is awaiting review"}

    def get_onboarding(self, user: EndUser) -> dict:
        """获取用户已提交的资料。"""
        onboarding = UserOnboarding.objects.filter(user=user).first()
        if not onboarding:
            return None
        agent_name = ""
        if onboarding.agent_code:
            try:
                agent = self._resolve_agent_by_code(onboarding.agent_code)
                agent_name = agent.agent_name if agent else ""
            except BusinessException:
                agent_name = ""
        return {
            "basic": {
                "legal_name": onboarding.legal_name,
                "id_type": onboarding.id_type,
                "id_number": onboarding.id_number,
                "contact_phone": onboarding.contact_phone,
                "nationality": onboarding.nationality,
                "address": onboarding.address,
                "agent_code": onboarding.agent_code,
                "agent_name": agent_name,
                "license_expiry_date": onboarding.license_expiry_date,
            },
            "finance": {
                "bank_name": onboarding.bank_name,
                "branch_name": onboarding.branch_name,
                "account_name": onboarding.account_name,
                "bank_account": onboarding.bank_account,
                "swift_code": onboarding.swift_code,
            },
            "images": {
                "license_image": onboarding.license_image,
                "id_front_image": onboarding.id_front_image,
                "id_back_image": onboarding.id_back_image,
            },
        }

    @staticmethod
    def agent_review_payload(user: EndUser) -> dict:
        try:
            onboarding = user.onboarding
        except UserOnboarding.DoesNotExist:
            onboarding = None
        if not onboarding:
            return {
                "agent_review_status": UserOnboarding.AgentReviewStatus.NONE,
                "agent_reviewed_at": None,
                "agent_reviewer": "",
                "agent_remark": "",
            }
        return {
            "agent_review_status": onboarding.agent_review_status or UserOnboarding.AgentReviewStatus.NONE,
            "agent_reviewed_at": onboarding.agent_reviewed_at,
            "agent_reviewer": onboarding.agent_reviewer,
            "agent_remark": onboarding.agent_remark,
        }

    @staticmethod
    def _awaiting_agent_review(user: EndUser) -> bool:
        try:
            return user.onboarding.agent_review_status == UserOnboarding.AgentReviewStatus.PENDING
        except UserOnboarding.DoesNotExist:
            return False

    @classmethod
    def _require_ops_reviewable(cls, user: EndUser):
        if cls._awaiting_agent_review(user):
            raise BusinessException(
                "AGENT_REVIEW_REQUIRED",
                "This customer must be reviewed by the agent before operations can review it",
                409,
            )

    # ── 审核 ──────────────────────────────────────────────

    @transaction.atomic
    def start_onboarding_review(self, user: EndUser) -> dict:
        """运营打开资料详情时，将 pending 标记为 under_review。"""
        user = EndUser.objects.select_for_update().select_related("onboarding").get(pk=user.pk)
        self._require_ops_reviewable(user)
        if user.onboarding_status == "pending":
            user.onboarding_status = "under_review"
            user.save(update_fields=["onboarding_status"])
        return {
            "status": user.onboarding_status,
            "onboarding_status": user.onboarding_status,
        }

    @transaction.atomic
    def review_onboarding(self, user: EndUser, action: str, remark: str = "", reviewer: str = "") -> dict:
        """一次审核：通过后创建客户或代理，并完成 KYC 激活。"""
        from decimal import Decimal

        from apps.agent.models import AgentKYC
        from apps.merchant.models import MerchantKYC
        from apps.merchant.services import MerchantService

        user = EndUser.objects.select_for_update().select_related("onboarding").get(pk=user.pk)
        self.ensure_portal_role(user)
        user.refresh_from_db()
        if user.onboarding_status not in ("pending", "under_review"):
            raise BusinessException(
                "ONBOARDING_STATUS_INVALID",
                f"Onboarding is currently {user.onboarding_status} and may not be reviewed again",
                409,
            )
        self._require_ops_reviewable(user)
        portal_role = user.portal_role or "customer"
        if action == "approve":
            user.onboarding_status = "approved"
            user.is_verified = True
            if portal_role == "agent":
                agent = self._create_agent_from_onboarding(user) or user.default_agent
                if agent:
                    user.default_agent = agent
            else:
                merchant = self._create_merchant_from_onboarding(user) or user.default_merchant
                if merchant:
                    user.default_merchant = merchant
                    self._bind_merchant_from_onboarding_agent_code(user, merchant)
        elif action == "reject":
            user.onboarding_status = "rejected"
            user.is_verified = False
        else:
            raise BusinessException("INVALID_ACTION", "The review action is invalid")

        user.onboarding_reviewed_at = timezone.now()
        user.onboarding_reviewer = reviewer
        user.onboarding_remark = remark
        user.save(update_fields=[
            "onboarding_status", "onboarding_reviewed_at",
            "onboarding_reviewer", "onboarding_remark",
            "is_verified", "default_merchant", "default_agent",
        ])

        merchant = user.default_merchant
        agent = user.default_agent
        agent_kyc_status = ""
        if action == "approve" and portal_role == "agent" and agent:
            agent.refresh_from_db()
            try:
                kyc = agent.kyc
            except AgentKYC.DoesNotExist:
                kyc = None
            if kyc and kyc.kyc_status != AgentKYC.KycStatus.APPROVED:
                self._activate_agent_after_review(agent, kyc, reviewer, remark)
                agent.refresh_from_db()
            try:
                agent_kyc_status = agent.kyc.kyc_status
            except AgentKYC.DoesNotExist:
                agent_kyc_status = ""

        if action == "approve" and portal_role != "agent" and merchant:
            merchant.refresh_from_db()
            try:
                kyc = merchant.kyc
            except MerchantKYC.DoesNotExist:
                kyc = None
            if kyc and kyc.kyc_status == MerchantKYC.Status.PENDING:
                MerchantService().review_kyc(
                    merchant,
                    {
                        "action": "approve",
                        "risk_level": "MEDIUM",
                        "fee_model": "PERCENTAGE",
                        "fee_rate": Decimal("0.003"),
                        "fixed_fee": Decimal("0"),
                        "min_fee": Decimal("0"),
                        "reason": remark,
                    },
                    actor=reviewer,
                )
                merchant.refresh_from_db()

        kyc_status = ""
        if merchant:
            try:
                kyc_status = merchant.kyc.kyc_status
            except MerchantKYC.DoesNotExist:
                kyc_status = ""
        approved_label = (
            "The application has been approved and the agent has been activated"
            if portal_role == "agent"
            else "The application has been approved and the customer has been activated"
        )
        return {
            "message": (
                approved_label
                if action == "approve"
                else "The profile review has been rejected"
            ),
            "status": user.onboarding_status,
            "next_stage": "ACTIVE" if action == "approve" else "ONBOARDING_RESUBMIT",
            "merchant_no": merchant.merchant_no if merchant else "",
            "merchant_status": merchant.status if merchant else "",
            "merchant_kyc_status": kyc_status,
            "portal_role": portal_role,
            "agent_no": agent.agent_no if agent else "",
            "agent_status": agent.status if agent else "",
            "agent_kyc_status": agent_kyc_status,
        }

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
        if not license_expiry_date:
            license_expiry_date = timezone.localdate() + timedelta(days=365)

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

        MerchantKYC.objects.create(
            merchant=merchant,
            legal_person=(onboarding.legal_name if onboarding else "") or legal_person_name,
            id_type=(onboarding.id_type if onboarding else "") or "ID_CARD",
            id_number=encrypt_field((onboarding.id_number if onboarding else "") or ""),
            id_number_plain=(onboarding.id_number if onboarding else "") or "",
            nationality=(onboarding.nationality if onboarding else "") or "",
            registered_address=(onboarding.address if onboarding else "") or "",
            kyc_status="PENDING",
        )

        if onboarding and (onboarding.bank_name or onboarding.bank_account):
            MerchantSettlementAccount.objects.create(
                merchant=merchant,
                bank_name=onboarding.bank_name or "",
                bank_branch=onboarding.branch_name or "",
                account_name=onboarding.account_name or onboarding.legal_name or merchant_name,
                account_number=onboarding.bank_account or "",
                is_default=True,
            )

        return merchant

    @staticmethod
    def _resolve_agent_by_code(agent_code: str):
        """Resolve a customer-entered Agent Code. Empty is allowed; invalid raises."""
        from apps.agent.models import Agent

        code = (agent_code or "").strip()
        if not code:
            return None
        qs = Agent.objects.filter(is_deleted=False)
        agent = qs.filter(agent_no=code).first()
        if not agent:
            matches = list(qs.filter(agent_no__iexact=code)[:2])
            agent = matches[0] if len(matches) == 1 else None
        if not agent:
            raise BusinessException(
                "AGENT_CODE_INVALID",
                "The Agent Code does not match an existing agent",
                400,
                field="agent_code",
            )
        return agent

    @staticmethod
    def _link_merchant_to_agent(agent, merchant):
        """Bind a customer to an agent for My customers and ops agent–customer links."""
        from decimal import Decimal

        from apps.agent.models import AgentMerchant

        if not agent or not merchant:
            return
        if merchant.agent_id != agent.id:
            merchant.agent = agent
            merchant.save(update_fields=["agent", "updated_at"])
        relation = AgentMerchant.objects.filter(agent=agent, merchant=merchant).first()
        if relation:
            if relation.is_deleted:
                relation.is_deleted = False
                relation.commission_rate = agent.commission_rate or relation.commission_rate
                relation.effective_from = relation.effective_from or timezone.localdate()
                relation.save(update_fields=[
                    "is_deleted", "commission_rate", "effective_from", "updated_at",
                ])
            return
        AgentMerchant.objects.create(
            agent=agent,
            merchant=merchant,
            commission_rate=agent.commission_rate or Decimal("0"),
            effective_from=timezone.localdate(),
        )

    @classmethod
    def _bind_merchant_from_onboarding_agent_code(cls, user: EndUser, merchant):
        try:
            onboarding = user.onboarding
        except UserOnboarding.DoesNotExist:
            return
        try:
            agent = cls._resolve_agent_by_code(onboarding.agent_code)
        except BusinessException:
            return
        cls._link_merchant_to_agent(agent, merchant)

    @staticmethod
    def _map_agent_kyc_id_type(id_type: str) -> str:
        mapping = {
            "id_card": "ID_CARD",
            "passport": "PASSPORT",
            "business_license": "BUSINESS_LICENSE",
            "ID_CARD": "ID_CARD",
            "PASSPORT": "PASSPORT",
            "BUSINESS_LICENSE": "BUSINESS_LICENSE",
        }
        return mapping.get((id_type or "").strip(), "ID_CARD")

    @staticmethod
    def _portal_contact_email(user: EndUser) -> str:
        email = (user.email or "").strip()
        if not email or email.endswith("@placeholder.local"):
            return ""
        return email

    @staticmethod
    def _activate_agent_after_review(agent, kyc, reviewer: str, remark: str = ""):
        from apps.agent.services import ensure_agent_accounts, ensure_agent_api_credentials

        kyc.kyc_status = kyc.KycStatus.UNDER_REVIEW
        kyc.approve(reviewer=reviewer or "ops", comment=remark or "Approved")
        if agent.status != "ACTIVE":
            agent.status = "ACTIVE"
            agent.save(update_fields=["status", "updated_at"])
        ensure_agent_api_credentials(agent)
        ensure_agent_accounts(agent)

    @staticmethod
    def _create_agent_from_onboarding(user: EndUser):
        """审核通过后，根据 onboarding 资料创建 Agent 与 AgentKYC。"""
        from apps.agent.models import Agent, AgentKYC
        from apps.agent.services import generate_agent_no

        if user.default_agent_id:
            return None

        onboarding = None
        try:
            onboarding = user.onboarding
        except Exception:
            pass
        legal_name = ""
        contact_phone = ""
        if onboarding:
            legal_name = onboarding.legal_name or ""
            contact_phone = onboarding.contact_phone or ""
        if not legal_name:
            legal_name = user.real_name or user.username or f"Agent {str(user.id)[:8]}"

        agent_name = legal_name[:128]
        legal_person = legal_name[:64]
        id_number = (onboarding.id_number if onboarding else "") or ""
        address = (onboarding.address if onboarding else "") or ""
        license_path = (onboarding.license_image if onboarding else "") or ""

        agent = Agent.objects.create(
            agent_no=generate_agent_no(),
            agent_name=agent_name,
            short_name=agent_name[:64],
            status="SUSPENDED",
            contact_name=legal_person,
            contact_phone=contact_phone or user.phone or "",
            contact_email=UserService._portal_contact_email(user),
            legal_person=legal_person,
            id_type=UserService._map_agent_kyc_id_type(onboarding.id_type if onboarding else ""),
            legal_person_id=id_number[:64],
            business_license_no=id_number[:64],
            business_license_file=license_path[:512],
            registered_address=address[:256],
            settlement_bank_name="",
            settlement_account_no="",
            swift_code="",
            settlement_account_holder=agent_name[:128],
        )
        AgentKYC.objects.create(
            agent=agent,
            legal_person=legal_person,
            id_type=UserService._map_agent_kyc_id_type(onboarding.id_type if onboarding else ""),
            id_number=encrypt_field(id_number),
            id_number_plain=id_number[:64],
            business_license=encrypt_field(id_number or "-"),
            registered_address=address[:256],
            kyc_status=AgentKYC.KycStatus.SUBMITTED,
            submitted_at=timezone.now(),
        )
        return agent

    # ── 信息管理 ──────────────────────────────────────────

    def get_profile(self, user: EndUser) -> dict:
        from apps.account.models import UserAccount
        from apps.account.models import UserPaymentDetail
        from apps.agent.models import AgentKYC
        from apps.merchant.models import MerchantKYC

        self.ensure_portal_role(user)
        user.refresh_from_db()

        bound_accounts = UserAccount.objects.filter(
            user_id=str(user.id), status=UserAccount.BindStatus.ACTIVE, is_deleted=False
        ).count()

        # 近3个月交易笔数
        three_months_ago = timezone.now() - timedelta(days=90)
        recent_count = UserPaymentDetail.objects.filter(
            user_id=str(user.id), is_deleted=False, created_at__gte=three_months_ago
        ).count()

        merchant = user.default_merchant
        agent = user.default_agent
        portal_role = user.portal_role or "none"
        try:
            kyc_status = merchant.kyc.kyc_status if merchant else ""
        except MerchantKYC.DoesNotExist:
            kyc_status = ""
        try:
            agent_kyc_status = agent.kyc.kyc_status if agent else ""
        except AgentKYC.DoesNotExist:
            agent_kyc_status = ""

        if portal_role == "agent":
            if user.onboarding_status != "approved":
                activation_stage = "ONBOARDING_REQUIRED"
            elif not agent:
                activation_stage = "AGENT_NOT_BOUND"
            elif agent.status == "ACTIVE":
                activation_stage = "ACTIVE"
            else:
                activation_stage = agent.status
            remittance_eligibility = {
                "eligible": False,
                "blockers": [{
                    "code": "AGENT_PORTAL",
                    "message": "Agent accounts use the agent workspace instead of remittance",
                    "field": "portal_role",
                }],
            }
        elif user.onboarding_status != "approved":
            activation_stage = "ONBOARDING_REQUIRED"
        elif not merchant:
            activation_stage = "MERCHANT_NOT_BOUND"
        elif merchant.status == "ACTIVE":
            activation_stage = "ACTIVE"
        elif kyc_status == MerchantKYC.Status.REJECTED:
            activation_stage = "KYC_REJECTED"
        elif merchant.status == "PENDING":
            activation_stage = "KYC_PENDING"
        else:
            activation_stage = merchant.status

        if portal_role != "agent":
            if user.onboarding_status != "approved":
                remittance_eligibility = {
                    "eligible": False,
                    "blockers": [{
                        "code": "ONBOARDING_REQUIRED",
                        "message": "Preliminary onboarding review must be completed first",
                        "field": "onboarding",
                    }],
                }
            elif not merchant:
                remittance_eligibility = {
                    "eligible": False,
                    "blockers": [{
                        "code": "MERCHANT_NOT_BOUND",
                        "message": "The account has not been bound to a customer",
                        "field": "merchant",
                    }],
                }
            else:
                from apps.payment.services.remittance_policy import RemittanceEligibilityPolicy
                remittance_eligibility = RemittanceEligibilityPolicy().evaluate(
                    merchant, include_usage=False
                ).as_dict()

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
            "portal_role": portal_role,
            "bound_accounts": bound_accounts,
            "recent_transactions": recent_count,
            "merchant_no": merchant.merchant_no if merchant else "",
            "merchant_name": merchant.merchant_name if merchant else "",
            "merchant_status": merchant.status if merchant else "",
            "merchant_kyc_status": kyc_status,
            "default_agent_id": str(agent.id) if agent else "",
            "agent_no": agent.agent_no if agent else "",
            "agent_status": agent.status if agent else "",
            "agent_kyc_status": agent_kyc_status,
            "activation_stage": activation_stage,
            "remittance_eligibility": remittance_eligibility,
            "license_expiry_date": merchant.license_expiry_date.isoformat() if (merchant and merchant.license_expiry_date) else "",
            "license_warning": self._get_user_license_warning(user),
            "created_at": user.created_at,
        }

    def require_bound_agent(self, user: EndUser):
        """Return the EndUser's bound Agent or raise 403."""
        from apps.agent.models import Agent

        self.ensure_portal_role(user)
        user.refresh_from_db()
        if (user.portal_role or "none") != "agent":
            raise BusinessException(
                "NOT_AGENT",
                "This workspace is available only to agent accounts",
                403,
            )
        if user.onboarding_status != "approved" or not user.default_agent_id:
            raise BusinessException(
                "AGENT_NOT_READY",
                "Agent onboarding must be approved before this information is available",
                403,
            )
        agent = Agent.objects.filter(pk=user.default_agent_id, is_deleted=False).first()
        if not agent:
            raise BusinessException(
                "AGENT_NOT_READY",
                "Agent onboarding must be approved before this information is available",
                403,
            )
        return agent

    def get_bound_agent_profile(self, user: EndUser) -> dict:
        from apps.agent.models import AgentKYC, AgentMerchant

        agent = self.require_bound_agent(user)
        try:
            kyc = agent.kyc
            kyc_status = kyc.kyc_status
            kyc_comment = kyc.review_comment
        except AgentKYC.DoesNotExist:
            kyc_status = ""
            kyc_comment = ""
        merchant_count = agent.direct_merchants.filter(is_deleted=False).count()
        relation_count = AgentMerchant.objects.filter(agent=agent, is_deleted=False).count()
        # Agent balance = SUM of bound customers' available balances (no agent-owned book).
        accounts = self._sum_bound_customer_balances(agent)
        return {
            "id": str(agent.id),
            "agent_no": agent.agent_no,
            "agent_name": agent.agent_name,
            "short_name": agent.short_name,
            "status": agent.status,
            "contact_name": agent.contact_name,
            "contact_phone": agent.contact_phone,
            "contact_email": agent.contact_email,
            "commission_rate": str(agent.commission_rate),
            "legal_person": agent.legal_person,
            "id_type": agent.id_type,
            "business_license_no": agent.business_license_no,
            "registered_address": agent.registered_address,
            "kyc_status": kyc_status,
            "kyc_comment": kyc_comment,
            "settlement_bank_name": agent.settlement_bank_name,
            "settlement_account_no": agent.settlement_account_no,
            "swift_code": agent.swift_code,
            "settlement_account_holder": agent.settlement_account_holder,
            "merchant_count": merchant_count,
            "relation_count": relation_count,
            "accounts": accounts,
        }

    def list_bound_agent_merchants(self, user: EndUser) -> list[dict]:
        from collections import defaultdict
        from decimal import Decimal

        from django.db.models import Q, Sum

        from apps.account.models import VirtualAccount
        from apps.agent.models import AgentMerchant
        from apps.merchant.models import Merchant
        from apps.payment.services.remittance_policy import RemittanceEligibilityPolicy

        agent = self.require_bound_agent(user)
        relations = {
            str(rel.merchant_id): rel
            for rel in AgentMerchant.objects.filter(agent=agent, is_deleted=False).select_related("merchant")
        }
        related_ids = [rel.merchant_id for rel in relations.values()]
        merchants = Merchant.objects.filter(is_deleted=False).filter(
            Q(agent=agent) | Q(pk__in=related_ids)
        ).order_by("-created_at")
        merchant_ids = [m.pk for m in merchants]
        end_users = {
            str(eu.default_merchant_id): str(eu.id)
            for eu in EndUser.objects.filter(
                default_merchant_id__in=merchant_ids,
                portal_role="customer",
                is_deleted=False,
            )
        }
        balance_rows = (
            VirtualAccount.objects.filter(
                is_deleted=False,
                merchant_id__in=merchant_ids,
            )
            .exclude(currency="")
            .values("merchant_id", "currency")
            .annotate(total=Sum("available_balance"))
        )
        balances_by_merchant: dict = defaultdict(list)
        for row in balance_rows:
            total = row["total"] or Decimal("0")
            balances_by_merchant[row["merchant_id"]].append({
                "currency": (row["currency"] or "").upper(),
                "available_balance": f"{total:.2f}",
            })
        for mid in balances_by_merchant:
            balances_by_merchant[mid].sort(key=lambda x: x["currency"])
        policy = RemittanceEligibilityPolicy()
        rows = []
        for merchant in merchants:
            rel = relations.get(str(merchant.id))
            rate = rel.commission_rate if rel else agent.commission_rate
            eligibility = policy.evaluate(merchant, include_usage=False)
            rows.append({
                "id": str(merchant.id),
                "merchant_no": merchant.merchant_no,
                "merchant_name": merchant.merchant_name,
                "status": merchant.status,
                "commission_rate": str(rate),
                "effective_from": rel.effective_from.isoformat() if rel and rel.effective_from else "",
                "effective_to": rel.effective_to.isoformat() if rel and rel.effective_to else "",
                "end_user_id": end_users.get(str(merchant.id), ""),
                "balances": balances_by_merchant.get(merchant.pk, []),
                "remittance_eligibility": eligibility.as_dict(),
            })
        return rows

    def resolve_bound_agent_merchant(self, user: EndUser, merchant_id: str):
        """Return a merchant bound to this agent or raise AGENT_MERCHANT_FORBIDDEN."""
        from apps.merchant.models import Merchant

        agent = self.require_bound_agent(user)
        merchant_id = str(merchant_id or "").strip()
        if not merchant_id:
            raise BusinessException(
                "MERCHANT_REQUIRED",
                "Please select a customer before requesting a quotation",
                400,
            )
        merchant = Merchant.objects.filter(pk=merchant_id, is_deleted=False).first()
        if not merchant:
            raise BusinessException("MERCHANT_NOT_FOUND", "The customer does not exist", 404)
        bound_ids = {str(pk) for pk in self._bound_agent_merchant_ids(agent)}
        if str(merchant.id) not in bound_ids:
            raise BusinessException(
                "AGENT_MERCHANT_FORBIDDEN",
                "This customer is not assigned to the current agent",
                403,
            )
        return agent, merchant

    def resolve_customer_user_id_for_merchant(self, merchant) -> str:
        customer = EndUser.objects.filter(
            default_merchant=merchant,
            portal_role="customer",
            is_deleted=False,
        ).first()
        return str(customer.id) if customer else ""

    def create_agent_remittance_quote(
        self,
        user: EndUser,
        *,
        merchant_id: str,
        amount,
        from_currency: str,
        to_currency: str,
        fee_bearing: str,
    ) -> dict:
        from apps.payment.services.remittance_quote import RemittanceQuoteService

        _agent, merchant = self.resolve_bound_agent_merchant(user, merchant_id)
        quote = RemittanceQuoteService().create_quote(
            merchant=merchant,
            amount=amount,
            from_currency=from_currency,
            to_currency=to_currency,
            fee_bearing=fee_bearing,
            actor_type="AGENT",
            user_id=str(user.id),
        )
        return RemittanceQuoteService.serialize(quote)

    def submit_agent_remittance(
        self,
        user: EndUser,
        *,
        merchant_id: str,
        payload: dict,
        idempotency_key: str,
    ):
        from apps.payment.services.remittance_application import RemittanceApplicationService

        _agent, merchant = self.resolve_bound_agent_merchant(user, merchant_id)
        order_user_id = self.resolve_customer_user_id_for_merchant(merchant)
        return RemittanceApplicationService().submit(
            merchant=merchant,
            payload=payload,
            idempotency_key=idempotency_key,
            user_id=str(user.id),
            actor_type="AGENT",
            order_user_id=order_user_id,
        )

    def list_bound_customer_virtual_accounts(
        self, user: EndUser, *, search="", status="", page=1, page_size=20,
    ) -> dict:
        from apps.account.models import VirtualAccount
        from apps.account.services import (
            apply_virtual_account_list_filters,
            group_virtual_accounts_by_customer,
            parse_page_params,
        )

        agent = self.require_bound_agent(user)
        merchant_ids = self._bound_agent_merchant_ids(agent)
        qs = VirtualAccount.objects.filter(merchant_id__in=merchant_ids)
        matched = apply_virtual_account_list_filters(qs, search=search, status=status)
        page, page_size = parse_page_params(page, page_size)
        return group_virtual_accounts_by_customer(matched, page=page, page_size=page_size)

    def bound_customer_virtual_account_stats(self, user: EndUser) -> dict:
        from apps.account.models import VirtualAccount
        from apps.account.services import virtual_account_status_stats

        agent = self.require_bound_agent(user)
        merchant_ids = self._bound_agent_merchant_ids(agent)
        qs = VirtualAccount.objects.filter(is_deleted=False, merchant_id__in=merchant_ids)
        return virtual_account_status_stats(qs)

    def get_bound_customer_va_transactions(self, user: EndUser, va_id: str) -> dict:
        from apps.account.models import VirtualAccount
        from apps.account.services import serialize_virtual_account_transactions

        agent = self.require_bound_agent(user)
        merchant_ids = self._bound_agent_merchant_ids(agent)
        va = (
            VirtualAccount.objects.filter(
                pk=va_id, is_deleted=False, merchant_id__in=merchant_ids,
            )
            .select_related("master_account", "merchant")
            .first()
        )
        if not va:
            raise BusinessException("VA_NOT_FOUND", "The virtual account does not exist", 404)
        return serialize_virtual_account_transactions(va)

    def _bound_agent_merchant_ids(self, agent) -> list:
        from django.db.models import Q

        from apps.agent.models import AgentMerchant
        from apps.merchant.models import Merchant

        related_ids = list(
            AgentMerchant.objects.filter(agent=agent, is_deleted=False).values_list("merchant_id", flat=True)
        )
        return list(
            Merchant.objects.filter(is_deleted=False).filter(
                Q(agent=agent) | Q(pk__in=related_ids)
            ).values_list("pk", flat=True)
        )

    def _paginate(self, page, page_size):
        try:
            page = max(int(page or 1), 1)
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = min(max(int(page_size or 20), 1), 100)
        except (TypeError, ValueError):
            page_size = 20
        return page, page_size

    def _agent_order_row(self, order) -> dict:
        from apps.payment.serializers import build_order_timeline

        merchant = order.merchant
        return {
            "order_no": order.order_no,
            "merchant_no": merchant.merchant_no if merchant else "",
            "merchant_name": merchant.merchant_name if merchant else "",
            "amount": str(order.amount),
            "currency": order.currency,
            "from_currency": order.from_currency,
            "to_currency": order.to_currency,
            "fee_amount": str(order.fee_amount),
            "fee_currency": order.fee_currency,
            "sender_total_amount": str(order.sender_total_amount),
            "settle_amount": str(order.settle_amount),
            "exchange_rate": str(order.exchange_rate) if order.exchange_rate else None,
            "fee_bearing": order.fee_bearing or "",
            "beneficiary_name": order.beneficiary_name or "",
            "beneficiary_bank": order.beneficiary_bank or "",
            "beneficiary_account": order.beneficiary_account or "",
            "beneficiary_swift": order.beneficiary_swift or "",
            "beneficiary_address": order.beneficiary_address or "",
            "remittance_purpose": order.remittance_purpose or "",
            "status": order.status,
            "agent_review_status": order.agent_review_status,
            "agent_reviewed_by": order.agent_reviewed_by or "",
            "agent_reviewed_at": order.agent_reviewed_at,
            "agent_review_comment": order.agent_review_comment or "",
            "agent_payout_request_status": order.agent_payout_request_status,
            "agent_payout_requested_by": order.agent_payout_requested_by or "",
            "agent_payout_requested_at": order.agent_payout_requested_at,
            "created_at": order.created_at,
            "closed_at": order.closed_at,
            "timeline": build_order_timeline(order),
        }

    def _agent_orders_qs(self, agent):
        from apps.payment.models import PaymentOrder

        merchant_ids = self._bound_agent_merchant_ids(agent)
        return PaymentOrder.objects.filter(
            is_deleted=False,
            merchant_id__in=merchant_ids,
        ).select_related("merchant").order_by("-created_at")

    def _get_agent_order(self, agent, order_no: str):
        from apps.payment.models import PaymentOrder

        order = PaymentOrder.objects.filter(
            order_no=order_no, is_deleted=False,
        ).select_related("merchant").first()
        if not order:
            raise BusinessException("ORDER_NOT_FOUND", "The payment instruction does not exist", 404)
        merchant_ids = {str(pk) for pk in self._bound_agent_merchant_ids(agent)}
        if str(order.merchant_id) not in merchant_ids:
            raise BusinessException(
                "AGENT_ORDER_FORBIDDEN",
                "This instruction is not assigned to the current agent",
                403,
            )
        return order

    def list_agent_orders(
        self, user: EndUser, *, stage: str = "", search: str = "", page: int = 1, page_size: int = 20,
    ) -> dict:
        from django.db.models import Q

        from apps.payment.models import PaymentOrder

        agent = self.require_bound_agent(user)
        base = self._agent_orders_qs(agent)
        pending_q = Q(agent_review_status=PaymentOrder.AgentReviewStatus.PENDING)
        approved_q = Q(agent_review_status=PaymentOrder.AgentReviewStatus.APPROVED)
        rejected_q = Q(agent_review_status=PaymentOrder.AgentReviewStatus.REJECTED)
        awaiting_payout_q = Q(
            status=PaymentOrder.OrderStatus.PAY_RECEIVED,
            agent_payout_request_status=PaymentOrder.AgentPayoutRequestStatus.PENDING,
        )
        stats = {
            "pending": base.filter(pending_q).count(),
            "agreed": base.filter(approved_q).count(),
            "rejected": base.filter(rejected_q).count(),
            "awaiting_payout": base.filter(awaiting_payout_q).count(),
            "total": base.count(),
        }
        qs = base
        if search:
            qs = qs.filter(
                Q(order_no__icontains=search)
                | Q(beneficiary_name__icontains=search)
                | Q(merchant__merchant_name__icontains=search)
                | Q(merchant__merchant_no__icontains=search)
            )
        stage_key = (stage or "").strip().lower()
        # ``all``: every order for bound merchants (customer + agent-proxy remittances).
        # Default remains the agent review queue for backward compatibility.
        if stage_key in ("", "needs_review"):
            qs = qs.filter(pending_q)
        elif stage_key in ("agreed", "approved"):
            qs = qs.filter(approved_q)
        elif stage_key == "rejected":
            qs = qs.filter(rejected_q)
        elif stage_key in ("awaiting_payout", "needs_payout"):
            qs = qs.filter(awaiting_payout_q)
        elif stage_key == "all":
            pass
        else:
            qs = qs.filter(pending_q)
        page, page_size = self._paginate(page, page_size)
        total = qs.count()
        items = [self._agent_order_row(row) for row in qs[(page - 1) * page_size: page * page_size]]
        return {
            "count": total,
            "total": total,
            "page": page,
            "page_size": page_size,
            "results": items,
            "items": items,
            "stats": stats,
        }

    def get_agent_order(self, user: EndUser, order_no: str) -> dict:
        agent = self.require_bound_agent(user)
        order = self._get_agent_order(agent, order_no)
        return self._agent_order_row(order)

    def review_agent_order(
        self, user: EndUser, order_no: str, action: str, remark: str = "", reviewer: str = "",
    ) -> dict:
        from apps.payment.services.remittance_application import RemittanceApplicationService

        agent = self.require_bound_agent(user)
        order = self._get_agent_order(agent, order_no)
        reviewed = RemittanceApplicationService().review_by_agent(
            order, action=action, remark=remark, reviewer=reviewer,
        )
        payload = self._agent_order_row(reviewed)
        agreed = (action or "").strip().lower() in ("agree", "approve")
        payload["message"] = (
            "The instruction has been agreed and sent to operations"
            if agreed
            else "The instruction has been rejected"
        )
        return payload

    def request_agent_payout(self, user: EndUser, order_no: str, reviewer: str = "") -> dict:
        from apps.payment.services.remittance_application import RemittanceApplicationService

        agent = self.require_bound_agent(user)
        order = self._get_agent_order(agent, order_no)
        updated = RemittanceApplicationService().request_payout_by_agent(
            order, reviewer=reviewer,
        )
        payload = self._agent_order_row(updated)
        payload["message"] = "Payout has been requested. Operations can now confirm the transfer."
        return payload

    @staticmethod
    def _agent_code_matches(agent_no: str, agent_code: str) -> bool:
        return bool(agent_no) and (agent_no or "").strip().lower() == (agent_code or "").strip().lower()

    def _agent_kyc_base_qs(self, agent):
        return EndUser.objects.filter(
            is_deleted=False,
            portal_role="customer",
            onboarding__agent_code__iexact=agent.agent_no,
        ).exclude(
            onboarding__agent_review_status=UserOnboarding.AgentReviewStatus.NONE,
        ).select_related("onboarding")

    def _agent_kyc_row(self, target: EndUser) -> dict:
        try:
            onboarding = target.onboarding
        except UserOnboarding.DoesNotExist:
            onboarding = None
        return {
            "id": str(target.id),
            "username": target.username,
            "email": target.email,
            "phone": target.phone or "",
            "legal_person": onboarding.legal_name if onboarding else "",
            "id_type": onboarding.id_type if onboarding else "",
            "onboarding_status": target.onboarding_status,
            "agent_review_status": (
                onboarding.agent_review_status if onboarding else UserOnboarding.AgentReviewStatus.NONE
            ),
            "submitted_at": target.onboarding_submitted_at,
            "agent_reviewed_at": onboarding.agent_reviewed_at if onboarding else None,
            "agent_reviewer": onboarding.agent_reviewer if onboarding else "",
            "agent_remark": onboarding.agent_remark if onboarding else "",
        }

    def _get_agent_kyc_target(self, agent, user_id: str) -> tuple[EndUser, UserOnboarding]:
        target = EndUser.objects.filter(
            pk=user_id, is_deleted=False, portal_role="customer",
        ).select_related("onboarding").first()
        if not target:
            raise BusinessException("USER_NOT_FOUND", "The user does not exist", 404)
        try:
            onboarding = target.onboarding
        except UserOnboarding.DoesNotExist as exc:
            raise BusinessException("USER_NOT_FOUND", "The user does not exist", 404) from exc
        if not self._agent_code_matches(agent.agent_no, onboarding.agent_code):
            raise BusinessException(
                "AGENT_KYC_FORBIDDEN",
                "This customer is not assigned to the current agent",
                403,
            )
        return target, onboarding

    def list_agent_kyc(
        self, user: EndUser, *, stage: str = "", search: str = "", page: int = 1, page_size: int = 20,
    ) -> dict:
        from django.db.models import Q

        agent = self.require_bound_agent(user)
        base = self._agent_kyc_base_qs(agent)
        pending_q = Q(onboarding__agent_review_status=UserOnboarding.AgentReviewStatus.PENDING)
        approved_q = Q(onboarding__agent_review_status=UserOnboarding.AgentReviewStatus.APPROVED)
        rejected_q = Q(onboarding__agent_review_status=UserOnboarding.AgentReviewStatus.REJECTED)
        stats = {
            "pending_profile": base.filter(pending_q).count(),
            "approved": base.filter(approved_q).count(),
            "rejected": base.filter(rejected_q).count(),
            "total": base.count(),
        }
        qs = base
        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
                | Q(onboarding__legal_name__icontains=search)
            )
        if stage in ("", "needs_review"):
            qs = qs.filter(pending_q)
        elif stage == "approved":
            qs = qs.filter(approved_q)
        elif stage == "rejected":
            qs = qs.filter(rejected_q)
        qs = qs.order_by("-onboarding_submitted_at")
        try:
            page = max(int(page or 1), 1)
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = min(max(int(page_size or 20), 1), 100)
        except (TypeError, ValueError):
            page_size = 20
        total = qs.count()
        items = [self._agent_kyc_row(row) for row in qs[(page - 1) * page_size: page * page_size]]
        return {
            "count": total,
            "total": total,
            "page": page,
            "page_size": page_size,
            "results": items,
            "items": items,
            "stats": stats,
        }

    def get_agent_kyc_detail(self, user: EndUser, user_id: str) -> dict:
        agent = self.require_bound_agent(user)
        target, _onboarding = self._get_agent_kyc_target(agent, user_id)
        payload = self.get_onboarding(target)
        row = self._agent_kyc_row(target)
        return {
            **row,
            "data": payload,
        }

    @transaction.atomic
    def review_agent_kyc(
        self, user: EndUser, user_id: str, action: str, remark: str = "", reviewer: str = "",
    ) -> dict:
        agent = self.require_bound_agent(user)
        target, _onboarding = self._get_agent_kyc_target(agent, user_id)
        target = EndUser.objects.select_for_update().select_related("onboarding").get(pk=target.pk)
        onboarding = target.onboarding
        if onboarding.agent_review_status != UserOnboarding.AgentReviewStatus.PENDING:
            raise BusinessException(
                "AGENT_KYC_STATUS_INVALID",
                "This application is not awaiting agent review",
                409,
            )
        if action == "approve":
            onboarding.agent_review_status = UserOnboarding.AgentReviewStatus.APPROVED
        elif action == "reject":
            onboarding.agent_review_status = UserOnboarding.AgentReviewStatus.REJECTED
            target.onboarding_status = "rejected"
            target.is_verified = False
            target.onboarding_reviewed_at = timezone.now()
            target.onboarding_reviewer = reviewer
            target.onboarding_remark = remark
            target.save(update_fields=[
                "onboarding_status", "is_verified",
                "onboarding_reviewed_at", "onboarding_reviewer", "onboarding_remark",
                "updated_at",
            ])
        else:
            raise BusinessException("INVALID_ACTION", "The review action is invalid")
        onboarding.agent_reviewed_at = timezone.now()
        onboarding.agent_reviewer = reviewer
        onboarding.agent_remark = remark
        onboarding.save(update_fields=[
            "agent_review_status", "agent_reviewed_at", "agent_reviewer", "agent_remark", "updated_at",
        ])
        return {
            "message": (
                "The application has been approved and is awaiting operations review"
                if action == "approve"
                else "The profile review has been rejected"
            ),
            **self._agent_kyc_row(target),
        }

    @staticmethod
    def _earnings_period_bounds(period: str):
        """Calendar-period start for agent earnings filters (local TZ)."""
        key = (period or "month").strip().lower()
        if key not in {"week", "month", "quarter", "year", "all"}:
            key = "month"
        if key == "all":
            return key, None, None

        now = timezone.localtime()
        today = now.date()
        if key == "week":
            start_date = today - timedelta(days=today.weekday())
        elif key == "month":
            start_date = today.replace(day=1)
        elif key == "quarter":
            q_month = ((today.month - 1) // 3) * 3 + 1
            start_date = today.replace(month=q_month, day=1)
        else:  # year
            start_date = today.replace(month=1, day=1)

        start = timezone.make_aware(
            datetime.combine(start_date, datetime.min.time()),
            timezone.get_current_timezone(),
        )
        return key, start, now

    @staticmethod
    def _fee_share_currency(share) -> str:
        po = getattr(share, "payment_order", None)
        if po:
            currency = (po.currency or po.from_currency or "").strip().upper()
            if currency:
                return currency
        return "CNY"

    def list_bound_agent_earnings(
        self,
        user: EndUser,
        *,
        page: int = 1,
        page_size: int = 20,
        period: str = "month",
        merchant_name: str = "",
    ) -> dict:
        from collections import defaultdict
        from decimal import Decimal

        from apps.settlement.models import FeeShare

        agent = self.require_bound_agent(user)
        period_key, period_start, period_end = self._earnings_period_bounds(period)
        merchant_name = (merchant_name or "").strip()

        qs = FeeShare.objects.filter(agent=agent, is_deleted=False).select_related(
            "payment_order"
        )
        if period_start is not None:
            qs = qs.filter(created_at__gte=period_start)
        if merchant_name:
            qs = qs.filter(merchant_name=merchant_name)
        qs = qs.order_by("-created_at")

        summary_map: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        summary_count: dict[str, int] = defaultdict(int)
        customer_map: dict[tuple[str, str], dict] = {}

        for share in qs:
            currency = self._fee_share_currency(share)
            fee = Decimal(str(share.agent_fee or 0))
            summary_map[currency] += fee
            summary_count[currency] += 1
            key = (share.merchant_name or "", currency)
            row = customer_map.get(key)
            if not row:
                row = {
                    "merchant_name": share.merchant_name or "",
                    "currency": currency,
                    "agent_fee_total": Decimal("0"),
                    "order_count": 0,
                }
                customer_map[key] = row
            row["agent_fee_total"] += fee
            row["order_count"] += 1

        summary = [
            {
                "currency": ccy,
                "agent_fee_total": f"{summary_map[ccy]:.2f}",
                "order_count": summary_count[ccy],
            }
            for ccy in sorted(summary_map.keys())
        ]
        by_customer = sorted(
            [
                {
                    "merchant_name": row["merchant_name"],
                    "currency": row["currency"],
                    "agent_fee_total": f"{row['agent_fee_total']:.2f}",
                    "order_count": row["order_count"],
                }
                for row in customer_map.values()
            ],
            key=lambda r: (-Decimal(r["agent_fee_total"]), r["merchant_name"], r["currency"]),
        )

        total = qs.count()
        try:
            page = max(int(page or 1), 1)
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = min(max(int(page_size or 20), 1), 100)
        except (TypeError, ValueError):
            page_size = 20

        items = []
        for share in qs[(page - 1) * page_size: page * page_size]:
            items.append({
                "id": str(share.id),
                "order_no": share.order_no,
                "merchant_name": share.merchant_name,
                "agent_fee": str(share.agent_fee),
                "amount": str(share.amount),
                "currency": self._fee_share_currency(share),
                "created_at": share.created_at,
            })

        return {
            "period": period_key,
            "period_start": period_start,
            "period_end": period_end,
            "summary": summary,
            "by_customer": by_customer,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    def list_bound_agent_nostro_accounts(self, user: EndUser) -> list[dict]:
        """Agent has no operable nostro book; return empty for portal transfers UI."""
        self.require_bound_agent(user)
        return []

    @staticmethod
    def _agent_has_no_account():
        raise BusinessException(
            "AGENT_HAS_NO_ACCOUNT",
            "Agents do not hold a system book balance. View bound customers' accounts instead.",
            400,
        )

    def _sum_bound_customer_balances(self, agent) -> list[dict]:
        """Sum available_balance of bound customer VAs, grouped by currency."""
        from decimal import Decimal

        from django.db.models import Sum

        from apps.account.models import VirtualAccount

        merchant_ids = self._bound_agent_merchant_ids(agent)
        if not merchant_ids:
            return []
        rows = (
            VirtualAccount.objects.filter(
                is_deleted=False,
                merchant_id__in=merchant_ids,
            )
            .exclude(currency="")
            .values("currency")
            .annotate(total=Sum("available_balance"))
            .order_by("currency")
        )
        return [
            {
                "currency": (row["currency"] or "").upper(),
                "balance": f"{(row['total'] or Decimal('0')):.2f}",
            }
            for row in rows
            if row["currency"]
        ]

    @staticmethod
    def _serialize_deposit(deposit) -> dict:
        return {
            "id": str(deposit.id),
            "deposit_no": deposit.deposit_no,
            "source": deposit.source,
            "currency": deposit.currency,
            "amount": str(deposit.amount),
            "status": deposit.status,
            "remark": deposit.remark,
            "merchant_name": deposit.merchant.merchant_name if deposit.merchant_id else "",
            "agent_name": deposit.agent.agent_name if deposit.agent_id else "",
            "reviewed_at": deposit.reviewed_at,
            "review_comment": deposit.review_comment,
            "created_at": deposit.created_at,
        }

    def list_bound_agent_currency_accounts(self, user: EndUser) -> dict:
        agent = self.require_bound_agent(user)
        return {"items": self._sum_bound_customer_balances(agent)}

    def enable_bound_agent_currency(self, user: EndUser, currency: str) -> dict:
        self.require_bound_agent(user)
        self._agent_has_no_account()

    def list_bound_agent_deposits(self, user: EndUser, *, page: int = 1, page_size: int = 20) -> dict:
        from apps.account.models import DepositRequest

        agent = self.require_bound_agent(user)
        merchant_ids = self._bound_agent_merchant_ids(agent)
        qs = DepositRequest.objects.filter(
            is_deleted=False,
            source=DepositRequest.DepositSource.CUSTOMER,
            merchant_id__in=merchant_ids,
        ).select_related("merchant", "agent").order_by("-created_at")
        total = qs.count()
        try:
            page = max(int(page or 1), 1)
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = min(max(int(page_size or 20), 1), 100)
        except (TypeError, ValueError):
            page_size = 20
        items = [self._serialize_deposit(row) for row in qs[(page - 1) * page_size: page * page_size]]
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    def create_bound_agent_deposit(self, user: EndUser, *, currency: str, amount, remark: str = "") -> dict:
        self.require_bound_agent(user)
        self._agent_has_no_account()

    def create_customer_virtual_top_up(self, user: EndUser, *, currency: str, amount, remark: str = "") -> dict:
        from apps.account.services import AccountService

        merchant = user.default_merchant
        if not merchant:
            raise BusinessException(
                "MERCHANT_NOT_BOUND",
                "No customer entity is linked to this account. Contact operations.",
            )
        deposit = AccountService().create_customer_deposit(
            merchant=merchant, currency=currency, amount=amount, remark=remark,
        )
        return self._serialize_deposit(deposit)


    def list_bound_agent_fund_transfers(self, user: EndUser, *, page: int = 1, page_size: int = 50) -> dict:
        self.require_bound_agent(user)
        return {"total": 0, "page": 1, "page_size": page_size, "items": []}

    def create_bound_agent_fund_transfer(
        self,
        user: EndUser,
        *,
        from_account_id: str,
        to_account_id: str,
        amount,
        remark: str = "",
    ) -> dict:
        self.require_bound_agent(user)
        self._agent_has_no_account()

    def execute_bound_agent_fund_transfer(self, user: EndUser, transfer_no: str) -> dict:
        self.require_bound_agent(user)
        self._agent_has_no_account()

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
            raise BusinessException("SMS_TOO_FREQUENT", "Verification codes are being requested too frequently; please retry after 60 seconds")

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
                raise BusinessException("SMS_PROVIDER_ERROR", "The SMS channel has not been configured")
        return {"phone": phone, "scene": scene, "expires_in": SMS_CODE_EXPIRE_MINUTES * 60}

    def _verify_sms_code(self, phone: str, code: str, scene: str):
        record = SmsCode.objects.filter(
            phone=phone, scene=scene, code=code, is_used=False,
            expires_at__gte=timezone.now(),
        ).order_by("-created_at").first()

        if not record:
            raise BusinessException("SMS_CODE_INVALID", "The verification code is incorrect or has expired")

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
