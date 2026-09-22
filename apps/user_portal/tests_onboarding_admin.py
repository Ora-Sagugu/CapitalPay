"""Ops onboarding queues are split by portal_role and require a conscious decision."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.rbac.services import AuthService
from apps.user_portal.models import EndUser
from apps.user_portal.services import UserService
from apps.user_portal.tests import (
    ONBOARDING_PAYLOAD,
    ensure_referral_agent,
    merchant_onboarding_payload,
)


class OnboardingAdminQueueTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.auth = AuthService()
        users = self.auth.ensure_ops_rbac()
        self.admin = users["admin"]
        self.ops = users["ops"]
        token = self.auth.admin_login("admin", "123456")["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        self.svc = UserService()
        ensure_referral_agent()
        self.svc.register(phone="13900000101", password="Test@123", sms_code="")
        self.merchant_user = EndUser.objects.get(phone="13900000101")
        self.svc.choose_role(self.merchant_user, "merchant")
        self.merchant_user.refresh_from_db()
        self.svc.submit_onboarding(self.merchant_user, merchant_onboarding_payload(
            legal_name="Queue Merchant Ltd",
            id_number="QM-001",
            contact_phone="13900000101",
        ))
        onboarding = self.merchant_user.onboarding
        onboarding.agent_review_status = onboarding.AgentReviewStatus.APPROVED
        onboarding.agent_reviewer = "test-agent"
        onboarding.save(update_fields=[
            "agent_review_status", "agent_reviewer", "updated_at",
        ])

        self.svc.register(phone="13900000102", password="Test@123", sms_code="")
        self.agent_user = EndUser.objects.get(phone="13900000102")
        self.svc.choose_role(self.agent_user, "agent")
        self.agent_user.refresh_from_db()
        self.svc.submit_onboarding(self.agent_user, {
            **ONBOARDING_PAYLOAD,
            "basic": {**ONBOARDING_PAYLOAD["basic"], "contact_phone": "13900000102"},
            "kyb": {
                "business": {"legal_name": "Queue Agent Ltd", "industry": "Payments"},
                "payout": {
                    "bank": "Stanbic",
                    "account_name": "Queue Agent Ltd",
                    "account_number": "998877",
                    "swift": "SBICZMLX",
                },
            },
        })

    def test_default_queue_is_merchant_only(self):
        res = self.client.get("/api/v1/admin/onboarding/", {"stage": "needs_review"})
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data["portal_role"], "merchant")
        ids = {row["id"] for row in res.data["results"]}
        self.assertIn(str(self.merchant_user.id), ids)
        self.assertNotIn(str(self.agent_user.id), ids)

    def test_agent_queue_excludes_merchants(self):
        res = self.client.get(
            "/api/v1/admin/onboarding/",
            {"stage": "needs_review", "portal_role": "agent"},
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data["portal_role"], "agent")
        ids = {row["id"] for row in res.data["results"]}
        self.assertIn(str(self.agent_user.id), ids)
        self.assertNotIn(str(self.merchant_user.id), ids)

    def test_ops_with_merchant_approve_cannot_review_agent(self):
        from apps.rbac.models import Role

        ops_role = Role.objects.get(code="merchant_ops")
        self.auth.set_role_capabilities(
            ops_role, ["feature:merchants", "feature:merchants.approve"],
        )
        token = self.auth.admin_login("ops", "123456")["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        res = self.client.post(
            f"/api/v1/admin/onboarding/{self.agent_user.id}/start-review/",
            {},
            format="json",
        )
        self.assertEqual(res.status_code, 403)

    def test_http_approve_requires_start_and_decision(self):
        payload = {
            "action": "approve",
            "risk_level": "HIGH",
            "enable_wire_transfer": True,
            "fee_model": "PERCENTAGE",
            "fee_rate": "0.005",
            "fixed_fee": "0",
            "min_fee": "0",
        }
        denied = self.client.post(
            f"/api/v1/admin/onboarding/{self.merchant_user.id}/review/",
            payload,
            format="json",
        )
        self.assertEqual(denied.status_code, 409, denied.content)
        self.assertEqual(denied.data["code"], "ONBOARDING_STATUS_INVALID")

        started = self.client.post(
            f"/api/v1/admin/onboarding/{self.merchant_user.id}/start-review/",
            {},
            format="json",
        )
        self.assertEqual(started.status_code, 200, started.content)
        missing = self.client.post(
            f"/api/v1/admin/onboarding/{self.merchant_user.id}/review/",
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(missing.status_code, 400, missing.content)

        approved = self.client.post(
            f"/api/v1/admin/onboarding/{self.merchant_user.id}/review/",
            payload,
            format="json",
        )
        self.assertEqual(approved.status_code, 200, approved.content)
        self.merchant_user.refresh_from_db()
        self.assertEqual(self.merchant_user.default_merchant.risk_level, "HIGH")
        fee = self.merchant_user.default_merchant.fees.filter(
            product_type="WIRE_TRANSFER", is_deleted=False,
        ).first()
        self.assertEqual(fee.fee_rate, Decimal("0.005"))

    def test_agent_approve_copies_kyb_and_settlement(self):
        started = self.client.post(
            f"/api/v1/admin/onboarding/{self.agent_user.id}/start-review/",
            {},
            format="json",
        )
        self.assertEqual(started.status_code, 200, started.content)
        approved = self.client.post(
            f"/api/v1/admin/onboarding/{self.agent_user.id}/review/",
            {
                "action": "approve",
                "kyc_tier": "TIER_2",
                "commission_rate": "0.15",
            },
            format="json",
        )
        self.assertEqual(approved.status_code, 200, approved.content)
        self.agent_user.refresh_from_db()
        agent = self.agent_user.default_agent
        self.assertEqual(agent.commission_rate, Decimal("0.150000"))
        self.assertEqual(agent.kyc.tier, "TIER_2")
        self.assertEqual(agent.settlement_bank_name, "Stanbic")
        self.assertEqual(agent.kyc.kyb_snapshot["payout"]["bank"], "Stanbic")

    def test_agent_approve_agrees_without_decision_fields(self):
        started = self.client.post(
            f"/api/v1/admin/onboarding/{self.agent_user.id}/start-review/",
            {},
            format="json",
        )
        self.assertEqual(started.status_code, 200, started.content)
        approved = self.client.post(
            f"/api/v1/admin/onboarding/{self.agent_user.id}/review/",
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(approved.status_code, 200, approved.content)
        self.agent_user.refresh_from_db()
        self.assertEqual(self.agent_user.onboarding_status, "approved")
        agent = self.agent_user.default_agent
        self.assertIsNotNone(agent)
        self.assertEqual(agent.kyc.tier, "TIER_1")
        self.assertEqual(agent.commission_rate, Decimal("0"))
        self.assertEqual(agent.settlement_bank_name, "Stanbic")
