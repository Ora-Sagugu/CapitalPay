"""Agent Code create/update, fee share, and onboarding sync."""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.agent.models import Agent, AgentCustomer
from apps.payment.models import PaymentOrder
from apps.rbac.models import SystemUser
from apps.rbac.testing import attach_super_admin
from apps.settlement.engine.calculator import SettlementCalculator


class ManualAgentCodeApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = SystemUser.objects.create(
            username="agent-ops",
            password_hash="test",
            real_name="Agent Ops",
        )
        attach_super_admin(self.user)
        self.client.force_authenticate(self.user)

    def test_create_persists_supplied_agent_no(self):
        response = self.client.post(
            "/api/v1/admin/agents/",
            {"agent_no": "AG-MANUAL-1", "agent_name": "Manual Agent"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["agent_no"], "AG-MANUAL-1")
        self.assertTrue(Agent.objects.filter(agent_no="AG-MANUAL-1").exists())

    def test_create_requires_agent_no(self):
        response = self.client.post(
            "/api/v1/admin/agents/",
            {"agent_name": "Missing Code"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_patch_changes_agent_no(self):
        agent = Agent.objects.create(agent_no="OLDCODE01", agent_name="Rename Me")
        response = self.client.patch(
            f"/api/v1/admin/agents/{agent.id}/",
            {"agent_no": "NEWCODE01"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        agent.refresh_from_db()
        self.assertEqual(agent.agent_no, "NEWCODE01")

    def test_duplicate_and_case_variant_rejected(self):
        Agent.objects.create(agent_no="Unique01", agent_name="First")
        duplicate = self.client.post(
            "/api/v1/admin/agents/",
            {"agent_no": "Unique01", "agent_name": "Copy"},
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400, duplicate.content)
        variant = self.client.post(
            "/api/v1/admin/agents/",
            {"agent_no": "unique01", "agent_name": "Case Copy"},
            format="json",
        )
        self.assertEqual(variant.status_code, 400, variant.content)


class AgentFeeShareApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = SystemUser.objects.create(
            username="fee-ops",
            password_hash="test",
            real_name="Fee Ops",
        )
        attach_super_admin(self.user)
        self.client.force_authenticate(self.user)
        self.agent = Agent.objects.create(
            agent_no="AG-FEE-1",
            agent_name="Fee Agent",
            commission_rate=Decimal("0.500000"),
        )
        self.customer = AgentCustomer.objects.create(
            agent=self.agent,
            legal_name="Fee Customer",
            kyc_status=AgentCustomer.KycStatus.APPROVED,
        )

    def test_patch_commission_rate_and_reject_out_of_range(self):
        ok = self.client.patch(
            f"/api/v1/admin/agents/{self.agent.id}/",
            {"commission_rate": "0.800000"},
            format="json",
        )
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertEqual(Decimal(str(ok.data["commission_rate"])), Decimal("0.800000"))
        listed = self.client.get("/api/v1/admin/agents/")
        self.assertEqual(listed.status_code, 200, listed.content)
        row = next(item for item in listed.data["results"] if item["id"] == str(self.agent.id))
        self.assertEqual(row["customer_count"], 1)
        self.assertEqual(row["order_count"], 0)
        bad = self.client.patch(
            f"/api/v1/admin/agents/{self.agent.id}/",
            {"commission_rate": "1.50"},
            format="json",
        )
        self.assertEqual(bad.status_code, 400, bad.content)

    def test_fee_overview_groups_orders_by_currency(self):
        usd = PaymentOrder.objects.create(
            order_no="RMT_FEE_USD_001",
            merchant_order_no="M_FEE_USD",
            unique_identification_no="UIN_FEE_USD",
            idempotency_key="IDEM_FEE_USD",
            merchant=None,
            agent=self.agent,
            agent_customer=self.customer,
            amount=Decimal("100.00"),
            currency="USD",
            from_currency="USD",
            fee_amount=Decimal("10.00"),
            settle_amount=Decimal("90.00"),
            status="PENDING_PAY",
            expire_at=timezone.now(),
        )
        PaymentOrder.objects.create(
            order_no="RMT_FEE_EUR_001",
            merchant_order_no="M_FEE_EUR",
            unique_identification_no="UIN_FEE_EUR",
            idempotency_key="IDEM_FEE_EUR",
            merchant=None,
            agent=self.agent,
            agent_customer=self.customer,
            amount=Decimal("50.00"),
            currency="EUR",
            from_currency="EUR",
            fee_amount=Decimal("4.00"),
            settle_amount=Decimal("46.00"),
            status="PENDING_PAY",
            expire_at=timezone.now(),
        )
        SettlementCalculator().calculate_fee_share(usd, channel_rate=Decimal("0"))
        overview = self.client.get(f"/api/v1/admin/agents/{self.agent.id}/fee-overview/")
        self.assertEqual(overview.status_code, 200, overview.content)
        self.assertEqual(overview.data["order_count"], 2)
        self.assertEqual(overview.data["customer_count"], 1)
        by_ccy = {row["currency"]: row for row in overview.data["by_currency"]}
        self.assertEqual(by_ccy["USD"]["order_count"], 1)
        self.assertEqual(by_ccy["USD"]["customer_fee"], "10.00")
        self.assertEqual(by_ccy["USD"]["agent_fee"], "5.00")
        self.assertEqual(by_ccy["EUR"]["order_count"], 1)
        self.assertEqual(by_ccy["EUR"]["agent_fee"], "0.00")
        self.assertEqual(len(overview.data["recent_orders"]), 2)
