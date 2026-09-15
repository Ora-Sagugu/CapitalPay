"""P0 核心能力 — 代理开户 / PRN API / VA 记账 / 拨付双审 / 对账预警。"""
import hashlib
import hmac
import time
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.account.models import NostroAccount, VaLedgerEntry, VirtualAccount, AgentDisbursement
from apps.account.services import DisbursementService, AccountService
from apps.agent.models import Agent, AgentKYC
from apps.agent.services import ensure_agent_accounts
from apps.merchant.models import Merchant, MerchantFee
from apps.merchant.services import MerchantService, ensure_merchant_virtual_account
from apps.payment.models import PaymentOrder, PrnIssuance
from apps.payment.services.payment import PaymentConfirmService
from apps.payment.services.pre_order import PreOrderService
from apps.reconciliation.alerts import fire_recon_alerts
from apps.reconciliation.models import ReconciliationBatch, ReconAlert
from apps.rbac.models import SystemUser


def _hmac_headers(api_key, secret, method, path, body=""):
    ts = str(int(time.time()))
    nonce = f"n{time.time_ns()}"
    sign_str = f"{api_key}{ts}{nonce}{method}{path}"
    if body:
        sign_str += body
    signature = hmac.new(secret.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    return {
        "HTTP_X_API_KEY": api_key,
        "HTTP_X_TIMESTAMP": ts,
        "HTTP_X_NONCE": nonce,
        "HTTP_X_SIGNATURE": signature,
        "content_type": "application/json",
    }


class AgentAutoAccountTests(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(agent_no="AG_P0_001", agent_name="P0 Agent")

    def test_ensure_agent_accounts_creates_current_and_fee(self):
        created = ensure_agent_accounts(self.agent)
        self.assertEqual(len(created), 2)
        types = set(self.agent.nostro_accounts.filter(is_deleted=False).values_list("account_type", flat=True))
        self.assertEqual(types, {NostroAccount.AccountType.CURRENT, NostroAccount.AccountType.FEE})
        self.assertEqual(self.agent.virtual_accounts.filter(va_type=VirtualAccount.VaType.VLA).count(), 2)
        for acc in self.agent.nostro_accounts.filter(is_deleted=False):
            self.assertEqual(acc.balance, Decimal("0"))

    def test_ensure_agent_accounts_idempotent(self):
        ensure_agent_accounts(self.agent)
        ensure_agent_accounts(self.agent)
        self.assertEqual(self.agent.nostro_accounts.filter(is_deleted=False).count(), 2)

    def test_kyc_approve_view_opens_accounts(self):
        kyc = AgentKYC.objects.create(
            agent=self.agent,
            legal_person="Li",
            id_number="X",
            id_number_plain="110101199001011234",
            business_license="BL",
        )
        kyc.submit()
        from apps.agent.views import AgentKYCViewSet
        from rest_framework.test import APIRequestFactory, force_authenticate
        from apps.rbac.models import SystemUser
        from apps.rbac.services import AuthService
        from apps.rbac.testing import attach_super_admin

        user = SystemUser.objects.create(
            username="p0_ops", password_hash=AuthService._hash_password("Secret@123"),
            real_name="Ops",
        )
        attach_super_admin(user)

        factory = APIRequestFactory()
        request = factory.post(f"/api/v1/admin/agent-kyc/{kyc.id}/review/", {"action": "approve"}, format="json")
        force_authenticate(request, user=user)
        view = AgentKYCViewSet.as_view({"post": "review_kyc"})
        response = view(request, pk=str(kyc.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.agent.nostro_accounts.filter(is_deleted=False).count(), 2)
        self.assertTrue(self.agent.api_key)


class AgentPrnApiTests(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(
            agent_no="AG_PRN_001", agent_name="PRN Agent",
            api_key="ak_agent_prn_001", api_secret="sk_agent_prn_secret",
        )
        self.client = APIClient()

    def test_apply_and_query_prn(self):
        path = "/api/v1/agent/prn/apply/"
        body = '{"amount":"100.00","currency":"CNY"}'
        headers = _hmac_headers(self.agent.api_key, self.agent.api_secret, "POST", path, body)
        resp = self.client.post(path, data=body, **headers)
        self.assertEqual(resp.status_code, 201, resp.content)
        prn = resp.json()["prn_code"]
        self.assertTrue(prn)
        self.assertEqual(len(prn), 6)
        self.assertTrue(prn.startswith("A"))
        self.assertTrue(prn[1:].isdigit())
        self.assertEqual(resp.json()["status"], "ISSUED")

        qpath = f"/api/v1/agent/prn/{prn}/"
        qh = _hmac_headers(self.agent.api_key, self.agent.api_secret, "GET", qpath)
        qresp = self.client.get(qpath, **qh)
        self.assertEqual(qresp.status_code, 200)
        self.assertEqual(qresp.json()["prn_code"], prn)


class VaLedgerConfirmTests(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(
            merchant_no="VA_M001", merchant_name="VA Merchant",
            api_key="ak_va_001", api_secret="sk_va",
            status=Merchant.Status.ACTIVE,
        )
        ensure_merchant_virtual_account(self.merchant)
        MerchantService().set_fee(self.merchant, {
            "product_type": MerchantFee.ProductType.WIRE_TRANSFER,
            "fee_model": MerchantFee.FeeModel.PERCENTAGE,
            "fee_rate": Decimal("0.003"),
            "effective_from": timezone.now().date(),
        })
        self.order = PreOrderService().create_pre_order(
            merchant_no="VA_M001",
            merchant_order_no="MO_VA_001",
            amount=Decimal("50000.00"),
            pay_method="WIRE_TRANSFER",
            bank_code="CMB",
        )

    def test_confirm_credits_va_ledger(self):
        va = VirtualAccount.objects.filter(merchant=self.merchant, is_deleted=False).first()
        self.assertIsNotNone(va)
        before = va.ledger_balance
        matched = PaymentConfirmService().auto_match_wire_transfer({
            "txn_id": "BANK_VA_001",
            "amount": Decimal("50000.00"),
            "remark": f"货款 {self.order.unique_identification_no} 已付",
            "txn_time": timezone.now(),
            "bank_code": "CMB",
        })
        self.assertIsNotNone(matched)
        va.refresh_from_db()
        self.assertEqual(va.ledger_balance, before + Decimal("50000.00"))
        self.assertTrue(VaLedgerEntry.objects.filter(order=self.order, entry_type="CREDIT").exists())
        # idempotent
        PaymentConfirmService().auto_match_wire_transfer({
            "txn_id": "BANK_VA_002",
            "amount": Decimal("50000.00"),
            "remark": f"货款 {self.order.unique_identification_no} 已付",
            "txn_time": timezone.now(),
            "bank_code": "CMB",
        })
        self.assertEqual(VaLedgerEntry.objects.filter(order=self.order, entry_type="CREDIT").count(), 1)


class DisbursementDualAuthTests(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(agent_no="AG_DISB_001", agent_name="Disb Agent")
        ensure_agent_accounts(self.agent, "CNY")
        current = self.agent.nostro_accounts.get(account_type=NostroAccount.AccountType.CURRENT)
        current.balance = Decimal("1000.00")
        current.save()
        va = self.agent.virtual_accounts.get(master_account=current)
        va.ledger_balance = Decimal("1000.00")
        va.available_balance = Decimal("1000.00")
        va.save()
        self.svc = DisbursementService()
        self.d = self.svc.submit(
            agent=self.agent, amount=Decimal("100.00"), currency="CNY",
            payee_bank_name="BOC", payee_account_no="6222", payee_account_holder="Payee",
        )

    def test_same_approver_rejected(self):
        self.svc.approve(self.d, "FIRST", "alice")
        self.d.refresh_from_db()
        with self.assertRaises(Exception) as ctx:
            self.svc.approve(self.d, "SECOND", "alice")
        self.assertIn("SAME_APPROVER", str(ctx.exception.code))

    def test_second_approve_api_auto_executes(self):
        self.svc.approve(self.d, "FIRST", "alice")
        client = APIClient()
        from apps.rbac.testing import attach_super_admin
        operator = SystemUser.objects.create(
            username="disbursement-operator",
            password_hash="test",
            real_name="Disbursement Operator",
        )
        attach_super_admin(operator)
        client.force_authenticate(operator)
        resp = client.post(
            f"/api/v1/admin/disbursements/{self.d.disbursement_no}/approve/",
            {"approver": "bob", "step": "SECOND"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.d.refresh_from_db()
        self.assertEqual(self.d.status, AgentDisbursement.DisbursementStatus.SUCCESS)


class ReconAlertTests(TestCase):
    def test_fire_alert_on_diffs(self):
        batch = ReconciliationBatch.objects.create(
            batch_no="RB_P0_001",
            bank_code="MOCK",
            bank_name="模拟银行",
            reconciliation_date=timezone.now().date(),
            diff_count=3,
            status="DIFF",
        )
        alert = fire_recon_alerts(batch, 3)
        self.assertIsNotNone(alert)
        self.assertEqual(ReconAlert.objects.filter(batch=batch).count(), 1)
        self.assertEqual(alert.status, ReconAlert.AlertStatus.OPEN)
