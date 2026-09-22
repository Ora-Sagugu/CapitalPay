"""用户端模块 — 单元测试。"""
from django.test import TestCase
from django.utils import timezone
from .models import EndUser, SmsCode, RefreshToken
from .services import UserService


class EndUserModelTest(TestCase):
    """终端用户模型测试。"""

    def test_create_user(self):
        user = EndUser.objects.create(
            phone="13800138000",
            password_hash="hashed",
            nickname="测试用户",
        )
        self.assertEqual(user.phone, "13800138000")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_verified)
        self.assertTrue(user.is_authenticated)
        self.assertFalse(user.is_anonymous)

    def test_phone_unique(self):
        EndUser.objects.create(phone="13800138001", password_hash="x")
        with self.assertRaises(Exception):
            EndUser.objects.create(phone="13800138001", password_hash="y")

    def test_soft_delete(self):
        user = EndUser.objects.create(phone="13800138002", password_hash="x")
        self.assertFalse(user.is_deleted)
        user.is_deleted = True
        user.save()
        self.assertTrue(user.is_deleted)


class UserServiceRegisterTest(TestCase):
    """用户注册服务测试。"""

    def setUp(self):
        self.svc = UserService()

    def test_register_success(self):
        result = self.svc.register(phone="13900000001", password="Test@123", sms_code="")
        self.assertIn("token", result)
        self.assertEqual(result["user"]["phone"], "139****0001")
        self.assertFalse(result["user"]["is_verified"])

    def test_register_with_portal_role(self):
        result = self.svc.register(
            phone="13900000003", password="Test@123", sms_code="", portal_role="agent",
        )
        self.assertEqual(result["user"]["portal_role"], "agent")
        user = EndUser.objects.get(phone="13900000003")
        self.assertEqual(user.portal_role, "agent")

    def test_register_rejects_ops_identity(self):
        with self.assertRaises(Exception) as ctx:
            self.svc.register(
                phone="13900000004", password="Test@123", sms_code="", portal_role="admin",
            )
        self.assertEqual(ctx.exception.code, "INVALID_ROLE")

    def test_register_duplicate_phone(self):
        self.svc.register(phone="13900000002", password="Test@123", sms_code="")
        with self.assertRaises(Exception) as ctx:
            self.svc.register(phone="13900000002", password="Test@123", sms_code="")
        self.assertEqual(ctx.exception.code, "PHONE_EXISTS")

    def test_register_by_email_normalizes_and_logs_in(self):
        result = self.svc.register_by_email(
            username="", email="GraceNyambura@gmail.com", password="123456",
            portal_role="agent",
        )
        self.assertEqual(result["user"]["email"], "gracenyambura@gmail.com")
        self.assertEqual(result["user"]["portal_role"], "agent")

        login = self.svc.login_by_email("gracenyambura@gmail.com", "123456", portal_role="agent")
        self.assertIn("token", login)


class UserServiceLoginTest(TestCase):
    """用户登录服务测试。"""

    def setUp(self):
        self.svc = UserService()
        self.svc.register(phone="13900000005", password="Login@123", sms_code="")

    def test_login_by_password_success(self):
        result = self.svc.login_by_password("13900000005", "Login@123", ip="127.0.0.1")
        self.assertIn("token", result)
        self.assertIn("refresh_token", result)
        self.assertEqual(result["user"]["phone"], "139****0005")

    def test_login_wrong_password(self):
        with self.assertRaises(Exception) as ctx:
            self.svc.login_by_password("13900000005", "Wrong", ip="127.0.0.1")
        self.assertEqual(ctx.exception.code, "LOGIN_FAILED")

    def test_login_nonexistent_user(self):
        with self.assertRaises(Exception) as ctx:
            self.svc.login_by_password("13800000000", "Test@123", ip="127.0.0.1")
        self.assertEqual(ctx.exception.code, "LOGIN_FAILED")

    def test_login_wrong_portal_rejected(self):
        self.svc.register(
            phone="13900000006", password="Login@123", sms_code="", portal_role="agent",
        )
        with self.assertRaises(Exception) as ctx:
            self.svc.login_by_password(
                "13900000006", "Login@123", ip="127.0.0.1", portal_role="merchant",
            )
        self.assertEqual(ctx.exception.code, "WRONG_PORTAL")

    def test_login_matching_portal_succeeds(self):
        self.svc.register(
            phone="13900000007", password="Login@123", sms_code="", portal_role="merchant",
        )
        result = self.svc.login_by_password(
            "13900000007", "Login@123", ip="127.0.0.1", portal_role="merchant",
        )
        self.assertEqual(result["user"]["portal_role"], "merchant")

    def test_login_locks_unassigned_identity(self):
        self.svc.register(phone="13900000008", password="Login@123", sms_code="")
        result = self.svc.login_by_password(
            "13900000008", "Login@123", ip="127.0.0.1", portal_role="agent",
        )
        self.assertEqual(result["user"]["portal_role"], "agent")
        user = EndUser.objects.get(phone="13900000008")
        self.assertEqual(user.portal_role, "agent")


class UserServiceProfileTest(TestCase):
    """用户资料服务测试。"""

    def setUp(self):
        self.svc = UserService()
        self.svc.register(phone="13900000010", password="Test@123", sms_code="")
        self.user = EndUser.objects.get(phone="13900000010")

    def test_get_profile(self):
        profile = self.svc.get_profile(self.user)
        self.assertEqual(profile["phone"], "139****0010")
        self.assertFalse(profile["is_verified"])

    def test_update_nickname(self):
        self.svc.update_profile(self.user, nickname="新昵称")
        self.user.refresh_from_db()
        self.assertEqual(self.user.nickname, "新昵称")

    def test_verify_identity(self):
        self.svc.verify_identity(self.user, real_name="张三", id_card="110101199001011234")
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)
        self.assertEqual(self.user.real_name, "张三")


class UserServiceSmsTest(TestCase):
    """短信验证码服务测试。"""

    def setUp(self):
        self.svc = UserService()

    def test_send_sms_code(self):
        result = self.svc.send_sms_code("13900000020", SmsCode.Scene.LOGIN)
        self.assertEqual(result["phone"], "13900000020")
        self.assertEqual(result["scene"], SmsCode.Scene.LOGIN)

    def test_send_sms_too_frequent(self):
        self.svc.send_sms_code("13900000021", SmsCode.Scene.LOGIN)
        with self.assertRaises(Exception) as ctx:
            self.svc.send_sms_code("13900000021", SmsCode.Scene.LOGIN)
        self.assertEqual(ctx.exception.code, "SMS_TOO_FREQUENT")


class UserServiceTokenTest(TestCase):
    """Token 相关测试。"""

    def setUp(self):
        self.svc = UserService()
        self.svc.register(phone="13900000030", password="Test@123", sms_code="")
        self.user = EndUser.objects.get(phone="13900000030")

    def test_refresh_token(self):
        result = self.svc.login_by_password("13900000030", "Test@123")
        new_result = self.svc.refresh_token(result["refresh_token"])
        self.assertIn("token", new_result)
        self.assertIn("refresh_token", new_result)
        self.assertNotEqual(result["refresh_token"], new_result["refresh_token"])

    def test_refresh_token_already_used(self):
        result = self.svc.login_by_password("13900000030", "Test@123")
        self.svc.refresh_token(result["refresh_token"])
        with self.assertRaises(Exception) as ctx:
            self.svc.refresh_token(result["refresh_token"])
        self.assertEqual(ctx.exception.code, "REFRESH_TOKEN_INVALID")


class UserServiceOnboardingReviewTest(TestCase):
    """一次审核即创建客户、通过 KYC 并激活。"""

    def setUp(self):
        self.svc = UserService()
        ensure_referral_agent()
        self.svc.register(phone="13900000040", password="Test@123", sms_code="")
        self.user = EndUser.objects.get(phone="13900000040")
        self.svc.choose_role(self.user, "merchant")
        self.user.refresh_from_db()
        self.svc.submit_onboarding(self.user, merchant_onboarding_payload(
            legal_name="Acme Ltd",
            id_number="1234567890",
            contact_phone="13900000040",
        ))
        self.user.refresh_from_db()

    def test_approve_activates_merchant_and_kyc(self):
        from apps.merchant.models import Merchant, MerchantFee, MerchantKYC, MerchantSettlementAccount

        result = ops_approve_onboarding(self.svc, self.user)
        self.user.refresh_from_db()
        merchant = self.user.default_merchant
        merchant.refresh_from_db()
        kyc = merchant.kyc

        self.assertEqual(result["next_stage"], "ACTIVE")
        self.assertEqual(result["merchant_status"], Merchant.Status.ACTIVE)
        self.assertEqual(result["merchant_kyc_status"], MerchantKYC.Status.APPROVED)
        self.assertEqual(self.user.onboarding_status, "approved")
        self.assertEqual(merchant.status, Merchant.Status.ACTIVE)
        self.assertEqual(kyc.kyc_status, MerchantKYC.Status.APPROVED)
        self.assertEqual(merchant.agent.agent_no, REFERRAL_AGENT_NO)
        self.assertTrue(
            MerchantFee.objects.filter(
                merchant=merchant,
                product_type=MerchantFee.ProductType.WIRE_TRANSFER,
                is_deleted=False,
            ).exists()
        )
        from apps.agent.models import Agent
        self.assertFalse(Agent.objects.filter(agent_name="Acme Ltd").exists())
        self.assertIsNone(self.user.default_agent)
        self.assertFalse(merchant.virtual_accounts.filter(is_deleted=False).exists())
        acct = MerchantSettlementAccount.objects.get(
            merchant=merchant, is_deleted=False, is_default=True
        )
        self.assertEqual(acct.bank_name, "GTBank")
        self.assertEqual(acct.account_number, "1122334455")

    def test_get_profile_includes_belonging_agent(self):
        ops_approve_onboarding(self.svc, self.user)
        self.user.refresh_from_db()
        profile = self.svc.get_profile(self.user)
        self.assertEqual(profile["agent_no"], REFERRAL_AGENT_NO)
        self.assertEqual(profile["agent_name"], "Default Referral Agent")
        self.assertIsNone(self.user.default_agent)

    def test_reject_does_not_create_active_merchant(self):
        agent_approve_onboarding(self.user)
        self.svc.start_onboarding_review(self.user)
        result = self.svc.review_onboarding(
            self.user, action="reject", remark="Documents unclear", reviewer="ops"
        )
        self.user.refresh_from_db()
        self.assertEqual(result["next_stage"], "ONBOARDING_RESUBMIT")
        self.assertEqual(self.user.onboarding_status, "rejected")
        self.assertIsNone(self.user.default_merchant)


ONBOARDING_PAYLOAD = {
    "basic": {
        "legal_name": "Nairobi Agents Ltd",
        "id_type": "id_card",
        "id_number": "AG-ID-001",
        "contact_phone": "13900000050",
        "address": "Westlands",
    },
    "images": {
        "license_image": "kyc/agent-license.png",
        "id_front_image": "kyc/agent-front.png",
        "id_back_image": "kyc/agent-back.png",
    },
}

REFERRAL_AGENT_NO = "AGREF001"


def ensure_referral_agent(agent_no: str = REFERRAL_AGENT_NO):
    """ACTIVE agent used by merchant onboarding tests that require Agent Code."""
    from decimal import Decimal

    from apps.agent.models import Agent

    agent, _ = Agent.objects.get_or_create(
        agent_no=agent_no,
        defaults={
            "agent_name": "Default Referral Agent",
            "status": "ACTIVE",
            "commission_rate": Decimal("0.010000"),
        },
    )
    if agent.status != "ACTIVE" or agent.is_deleted:
        agent.status = "ACTIVE"
        agent.is_deleted = False
        agent.save(update_fields=["status", "is_deleted", "updated_at"])
    return agent


def merchant_onboarding_payload(**basic_overrides):
    ensure_referral_agent()
    basic = {
        "legal_name": "Lagos Imports Ltd",
        "id_type": "id_card",
        "id_number": "CUST-ID-001",
        "contact_phone": "13900000071",
        "agent_code": REFERRAL_AGENT_NO,
    }
    basic.update(basic_overrides)
    return {
        "basic": basic,
        "finance": {
            "bank_name": "GTBank",
            "account_name": basic.get("legal_name") or "Lagos Imports Ltd",
            "bank_account": "1122334455",
        },
        "images": {
            "license_image": "kyc/c-license.png",
            "id_front_image": "kyc/c-front.png",
            "id_back_image": "kyc/c-back.png",
        },
    }


def agent_approve_onboarding(user, reviewer="test-agent"):
    """Mark merchant onboarding as agent-approved so ops review can proceed."""
    from apps.user_portal.models import UserOnboarding

    user.refresh_from_db()
    onboarding = user.onboarding
    onboarding.agent_review_status = UserOnboarding.AgentReviewStatus.APPROVED
    onboarding.agent_reviewed_at = timezone.now()
    onboarding.agent_reviewer = reviewer
    onboarding.save(update_fields=[
        "agent_review_status", "agent_reviewed_at", "agent_reviewer", "updated_at",
    ])


def ops_approve_onboarding(svc, user, reviewer="ops"):
    """Move pending → under_review → approved with a valid ops decision."""
    user.refresh_from_db()
    if (user.portal_role or "") == "merchant":
        agent_approve_onboarding(user)
    if user.onboarding_status == "pending":
        svc.start_onboarding_review(user)
        user.refresh_from_db()
    return svc.review_onboarding(
        user, action="approve", reviewer=reviewer,
    )


class PortalRoleTests(TestCase):
    def setUp(self):
        self.svc = UserService()
        self.svc.register(phone="13900000050", password="Test@123", sms_code="")
        self.user = EndUser.objects.get(phone="13900000050")

    def test_choose_role_locks_identity(self):
        result = self.svc.choose_role(self.user, "agent")
        self.user.refresh_from_db()
        self.assertEqual(result["portal_role"], "agent")
        self.assertEqual(self.user.portal_role, "agent")
        with self.assertRaises(Exception) as ctx:
            self.svc.choose_role(self.user, "merchant")
        self.assertEqual(ctx.exception.code, "ROLE_ALREADY_CHOSEN")

    def test_submit_requires_role(self):
        with self.assertRaises(Exception) as ctx:
            self.svc.submit_onboarding(self.user, ONBOARDING_PAYLOAD)
        self.assertEqual(ctx.exception.code, "ROLE_REQUIRED")

    def test_legacy_onboarding_user_is_treated_as_merchant(self):
        self.user.onboarding_status = "pending"
        self.user.save(update_fields=["onboarding_status"])
        profile = self.svc.get_profile(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.portal_role, "merchant")
        self.assertEqual(profile["portal_role"], "merchant")


class AgentOnboardingReviewTest(TestCase):
    def setUp(self):
        self.svc = UserService()
        self.svc.register(phone="13900000051", password="Test@123", sms_code="")
        self.user = EndUser.objects.get(phone="13900000051")
        self.svc.choose_role(self.user, "agent")
        self.user.refresh_from_db()
        self.svc.submit_onboarding(self.user, ONBOARDING_PAYLOAD)
        self.user.refresh_from_db()

    def test_approve_creates_agent_accounts_and_binding(self):
        from apps.account.models import NostroAccount
        from apps.agent.models import Agent, AgentKYC
        from apps.merchant.models import Merchant

        result = ops_approve_onboarding(self.svc, self.user)
        self.user.refresh_from_db()
        agent = self.user.default_agent
        self.assertIsNotNone(agent)
        self.assertEqual(result["agent_no"], agent.agent_no)
        self.assertEqual(result["agent_status"], "ACTIVE")
        self.assertEqual(result["agent_kyc_status"], AgentKYC.KycStatus.APPROVED)
        self.assertEqual(agent.status, "ACTIVE")
        self.assertEqual(agent.settlement_bank_name, "")
        self.assertEqual(agent.swift_code, "")
        self.assertEqual(agent.kyc.kyc_status, AgentKYC.KycStatus.APPROVED)
        types = set(agent.nostro_accounts.filter(is_deleted=False).values_list("account_type", flat=True))
        self.assertEqual(types, {NostroAccount.AccountType.CURRENT, NostroAccount.AccountType.FEE})
        self.assertIsNone(self.user.default_merchant)
        self.assertFalse(Merchant.objects.filter(merchant_name="Nairobi Agents Ltd").exists())
        profile = self.svc.get_bound_agent_profile(self.user)
        self.assertEqual(profile["agent_no"], agent.agent_no)
        self.assertNotIn("api_secret", profile)

    def test_agent_apis_do_not_leak_other_agents(self):
        from decimal import Decimal

        from apps.agent.models import Agent
        from apps.merchant.models import Merchant
        from apps.settlement.models import FeeShare

        ops_approve_onboarding(self.svc, self.user)
        self.user.refresh_from_db()
        mine = self.user.default_agent
        other = Agent.objects.create(agent_no="AG_LEAK_001", agent_name="Other Agent")
        Merchant.objects.create(
            merchant_no="M_LEAK_001",
            merchant_name="Other Customer",
            status=Merchant.Status.ACTIVE,
            agent=other,
        )
        FeeShare.objects.create(
            agent=other,
            order_no="RMT_LEAK_001",
            merchant_name="Other Customer",
            agent_name=other.agent_name,
            agent_fee=Decimal("12.00"),
            amount=Decimal("200.00"),
        )
        merchants = self.svc.list_bound_agent_merchants(self.user)
        earnings = self.svc.list_bound_agent_earnings(self.user)
        self.assertEqual(merchants, [])
        self.assertEqual(earnings["total"], 0)
        self.assertEqual(self.svc.get_bound_agent_profile(self.user)["agent_no"], mine.agent_no)

        other_user_result = self.svc.register(phone="13900000052", password="Test@123", sms_code="")
        other_user = EndUser.objects.get(id=other_user_result["user"]["id"])
        with self.assertRaises(Exception) as ctx:
            self.svc.get_bound_agent_profile(other_user)
        self.assertEqual(ctx.exception.code, "NOT_AGENT")


class MerchantAgentCodeBindingTest(TestCase):
    """Merchant registration requires Agent Code and binds on ops approve."""

    def setUp(self):
        from decimal import Decimal

        from apps.agent.models import Agent

        self.svc = UserService()
        self.svc.register(phone="13900000070", password="Test@123", sms_code="")
        self.agent_user = EndUser.objects.get(phone="13900000070")
        self.agent = Agent.objects.create(
            agent_no="kP8mQ2xR",
            agent_name="Referral Agent",
            status="ACTIVE",
            commission_rate=Decimal("0.010000"),
        )
        self.agent_user.portal_role = "agent"
        self.agent_user.default_agent = self.agent
        self.agent_user.onboarding_status = "approved"
        self.agent_user.save(update_fields=[
            "portal_role", "default_agent", "onboarding_status", "updated_at",
        ])

        self.svc.register(phone="13900000071", password="Test@123", sms_code="")
        self.customer = EndUser.objects.get(phone="13900000071")
        self.svc.choose_role(self.customer, "merchant")
        self.customer.refresh_from_db()
        self.payload = merchant_onboarding_payload(
            legal_name="Lagos Imports Ltd",
            contact_phone="13900000071",
            agent_code="kP8mQ2xR",
        )

    def test_missing_agent_code_is_rejected(self):
        payload = {**self.payload, "basic": {**self.payload["basic"], "agent_code": ""}}
        with self.assertRaises(Exception) as ctx:
            self.svc.submit_onboarding(self.customer, payload)
        self.assertEqual(ctx.exception.code, "AGENT_CODE_REQUIRED")

    def test_invalid_agent_code_rejected_on_submit(self):
        payload = {**self.payload, "basic": {**self.payload["basic"], "agent_code": "NOEXIST1"}}
        with self.assertRaises(Exception) as ctx:
            self.svc.submit_onboarding(self.customer, payload)
        self.assertEqual(ctx.exception.code, "AGENT_CODE_INVALID")

    def test_get_onboarding_includes_resolved_agent_name(self):
        self.svc.submit_onboarding(self.customer, self.payload)
        data = self.svc.get_onboarding(self.customer)
        self.assertEqual(data["basic"]["agent_code"], "kP8mQ2xR")
        self.assertEqual(data["basic"]["agent_name"], "Referral Agent")

    def test_approve_binds_merchant_under_agent(self):
        from apps.agent.models import AgentMerchant

        self.svc.submit_onboarding(self.customer, self.payload)
        ops_approve_onboarding(self.svc, self.customer)
        self.customer.refresh_from_db()
        merchant = self.customer.default_merchant
        self.assertIsNotNone(merchant)
        self.assertEqual(merchant.agent_id, self.agent.id)
        self.assertTrue(
            AgentMerchant.objects.filter(
                agent=self.agent, merchant=merchant, is_deleted=False,
            ).exists()
        )
        rows = self.svc.list_bound_agent_merchants(self.agent_user)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["merchant_no"], merchant.merchant_no)
        self.assertEqual(rows[0]["merchant_name"], "Lagos Imports Ltd")
        self.assertEqual(rows[0]["end_user_id"], str(self.customer.id))
        self.assertEqual(rows[0]["contact_email"], "")

    def test_list_bound_merchants_exposes_portal_email(self):
        self.svc.register_by_email(
            username="LilySky",
            email="lilysky@gmail.com",
            password="Test@123",
            portal_role="merchant",
        )
        merchant_user = EndUser.objects.get(email="lilysky@gmail.com")
        self.svc.submit_onboarding(merchant_user, merchant_onboarding_payload(
            legal_name="LilySky",
            contact_phone="13900000081",
            agent_code="kP8mQ2xR",
        ))
        ops_approve_onboarding(self.svc, merchant_user)
        rows = self.svc.list_bound_agent_merchants(self.agent_user)
        row = next(item for item in rows if item["merchant_name"] == "LilySky")
        self.assertEqual(row["contact_email"], "lilysky@gmail.com")
        self.assertEqual(row["end_user_id"], str(merchant_user.id))

    def test_agent_code_match_is_case_insensitive(self):
        payload = {**self.payload, "basic": {**self.payload["basic"], "agent_code": "kp8mq2xr"}}
        self.svc.submit_onboarding(self.customer, payload)
        ops_approve_onboarding(self.svc, self.customer)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.default_merchant.agent_id, self.agent.id)

    def test_ops_can_start_review_with_agent_code(self):
        self.svc.submit_onboarding(self.customer, self.payload)
        agent_approve_onboarding(self.customer)
        result = self.svc.start_onboarding_review(self.customer)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.onboarding_status, "under_review")
        self.assertIn("status", result)
