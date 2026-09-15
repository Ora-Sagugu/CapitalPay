"""Agent-first remittance review: submit routing, agree/reject, ops queue isolation."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from apps.core.exceptions import BusinessException
from apps.agent.models import Agent
from apps.exchange.models import ExchangeRate
from apps.payment.models import MerchantDailyRemittanceUsage, PaymentOrder
from apps.payment.serializers import build_order_timeline
from apps.payment.services.fund_trace import NEXT_HOP_BY_STATUS
from apps.payment.services.remittance_application import RemittanceApplicationService
from apps.payment.services.remittance_quote import RemittanceQuoteService
from apps.payment.tests_remittance_v2 import create_eligible_merchant, submit_payload
from apps.payment.views import PaymentOrderViewSet
from apps.rbac.models import Role, SystemUser, UserRole
from apps.user_portal.models import EndUser
from apps.user_portal.services import UserService
from apps.user_portal.tests import ONBOARDING_PAYLOAD


class AgentRemittanceReviewServiceTests(TestCase):
    def setUp(self):
        self.merchant = create_eligible_merchant("AR")
        ExchangeRate.objects.create(
            date=timezone.localdate(),
            from_currency="USD",
            to_currency="CNY",
            rate=Decimal("7"),
            source="TEST",
        )
        self.agent = Agent.objects.create(
            agent_no="AG_RMT_01",
            agent_name="Review Agent",
            status="ACTIVE",
        )

    def quote(self, *, actor_type="CUSTOMER", user_id="cust-1"):
        return RemittanceQuoteService().create_quote(
            merchant=self.merchant,
            amount=Decimal("1000"),
            from_currency="USD",
            to_currency="CNY",
            fee_bearing="OUR",
            actor_type=actor_type,
            user_id=user_id,
        )

    def submit(self, *, actor_type="CUSTOMER", user_id="cust-1", key="idem-agent-1"):
        quote = self.quote(actor_type=actor_type, user_id=user_id)
        return RemittanceApplicationService().submit(
            merchant=self.merchant,
            payload=submit_payload(quote),
            idempotency_key=key,
            user_id=user_id,
            actor_type=actor_type,
        )

    def test_submit_without_agent_stays_pending_review(self):
        order, created = self.submit()
        self.assertTrue(created)
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PENDING_REVIEW)
        self.assertEqual(order.agent_review_status, PaymentOrder.AgentReviewStatus.NONE)

    def test_submit_with_agent_goes_pending_agent_review(self):
        self.merchant.agent = self.agent
        self.merchant.save(update_fields=["agent", "updated_at"])
        order, created = self.submit()
        self.assertTrue(created)
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PENDING_AGENT_REVIEW)
        self.assertEqual(order.agent_review_status, PaymentOrder.AgentReviewStatus.PENDING)
        timeline = build_order_timeline(order)
        codes = [step["code"] for step in timeline]
        self.assertIn("agent_review", codes)
        agent_step = next(step for step in timeline if step["code"] == "agent_review")
        ops_step = next(step for step in timeline if step["code"] == "review")
        self.assertTrue(agent_step["active"])
        self.assertFalse(ops_step["verified"])
        self.assertFalse(ops_step["active"])

    def test_admin_submit_with_agent_skips_agent_queue(self):
        self.merchant.agent = self.agent
        self.merchant.save(update_fields=["agent", "updated_at"])
        order, _created = self.submit(actor_type="ADMIN", user_id="", key="idem-admin-1")
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PENDING_REVIEW)
        self.assertEqual(order.agent_review_status, PaymentOrder.AgentReviewStatus.NONE)

    def test_agent_submit_with_agent_skips_self_review_and_uses_order_user_id(self):
        self.merchant.agent = self.agent
        self.merchant.save(update_fields=["agent", "updated_at"])
        quote = self.quote(actor_type="AGENT", user_id="agent-user-1")
        order, created = RemittanceApplicationService().submit(
            merchant=self.merchant,
            payload=submit_payload(quote),
            idempotency_key="idem-agent-proxy-1",
            user_id="agent-user-1",
            actor_type="AGENT",
            order_user_id="customer-user-9",
        )
        self.assertTrue(created)
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PENDING_REVIEW)
        self.assertEqual(order.agent_review_status, PaymentOrder.AgentReviewStatus.NONE)
        self.assertEqual(order.user_id, "customer-user-9")
        self.assertEqual(order.quote.actor_type, "AGENT")
        self.assertEqual(order.quote.user_id, "agent-user-1")

    def test_agent_cannot_consume_customer_quote(self):
        self.merchant.agent = self.agent
        self.merchant.save(update_fields=["agent", "updated_at"])
        quote = self.quote(actor_type="CUSTOMER", user_id="cust-1")
        with self.assertRaises(BusinessException) as ctx:
            RemittanceApplicationService().submit(
                merchant=self.merchant,
                payload=submit_payload(quote),
                idempotency_key="idem-agent-steal",
                user_id="agent-user-1",
                actor_type="AGENT",
                order_user_id="cust-1",
            )
        self.assertEqual(ctx.exception.code, "QUOTE_OWNER_MISMATCH")

    @override_settings(ENABLE_AGENTS=False)
    def test_submit_skips_agent_queue_when_agents_disabled(self):
        self.merchant.agent = self.agent
        self.merchant.save(update_fields=["agent", "updated_at"])
        order, _created = self.submit(key="idem-disabled")
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PENDING_REVIEW)
        self.assertEqual(order.agent_review_status, PaymentOrder.AgentReviewStatus.NONE)

    def test_agent_agree_sends_to_ops_without_prn(self):
        self.merchant.agent = self.agent
        self.merchant.save(update_fields=["agent", "updated_at"])
        order, _created = self.submit()
        reviewed = RemittanceApplicationService().review_by_agent(
            order, action="agree", reviewer="agent-user",
        )
        self.assertEqual(reviewed.status, PaymentOrder.OrderStatus.PENDING_REVIEW)
        self.assertEqual(reviewed.agent_review_status, PaymentOrder.AgentReviewStatus.APPROVED)
        self.assertEqual(reviewed.agent_reviewed_by, "agent-user")
        self.assertIsNone(reviewed.prn_code)
        self.assertFalse(reviewed.reviewed_at)
        timeline = build_order_timeline(reviewed)
        ops_step = next(step for step in timeline if step["code"] == "review")
        self.assertTrue(ops_step["active"])
        self.assertFalse(ops_step["verified"])

    def test_agent_reject_closes_and_releases_usage(self):
        self.merchant.agent = self.agent
        self.merchant.save(update_fields=["agent", "updated_at"])
        order, _created = self.submit()
        usage = MerchantDailyRemittanceUsage.objects.get(merchant=self.merchant)
        self.assertEqual(usage.order_count, 1)
        reviewed = RemittanceApplicationService().review_by_agent(
            order, action="reject", remark="Incomplete beneficiary details", reviewer="agent-user",
        )
        self.assertEqual(reviewed.status, PaymentOrder.OrderStatus.CLOSED)
        self.assertEqual(reviewed.agent_review_status, PaymentOrder.AgentReviewStatus.REJECTED)
        usage.refresh_from_db()
        self.assertEqual(usage.order_count, 0)
        self.assertEqual(usage.total_amount, Decimal("0"))

    def test_agent_reject_requires_reason(self):
        self.merchant.agent = self.agent
        self.merchant.save(update_fields=["agent", "updated_at"])
        order, _created = self.submit()
        with self.assertRaises(BusinessException) as caught:
            RemittanceApplicationService().review_by_agent(order, action="reject", remark="")
        self.assertEqual(caught.exception.code, "REJECT_REASON_REQUIRED")

    def test_fund_trace_maps_agent_review_status(self):
        self.assertEqual(
            NEXT_HOP_BY_STATUS["PENDING_AGENT_REVIEW"],
            ("awaiting_agent_review", "agent_review"),
        )


class AgentRemittanceOpsQueueTests(TestCase):
    def setUp(self):
        self.merchant = create_eligible_merchant("AQ")
        expire = timezone.now() + timedelta(days=7)
        self.pending_agent = PaymentOrder.objects.create(
            order_no="RMT_AGENT_WAIT",
            merchant_order_no="M_AGENT_WAIT",
            unique_identification_no="UIN_AGENT_WAIT",
            idempotency_key="IDEM_AGENT_WAIT",
            merchant=self.merchant,
            amount=Decimal("100.00"),
            currency="CNY",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("1.00"),
            settle_amount=Decimal("99.00"),
            status=PaymentOrder.OrderStatus.PENDING_AGENT_REVIEW,
            agent_review_status=PaymentOrder.AgentReviewStatus.PENDING,
            pay_method="WIRE_TRANSFER",
            beneficiary_name="Wait Co",
            expire_at=expire,
        )
        self.pending_ops = PaymentOrder.objects.create(
            order_no="RMT_OPS_READY",
            merchant_order_no="M_OPS_READY",
            unique_identification_no="UIN_OPS_READY",
            idempotency_key="IDEM_OPS_READY",
            merchant=self.merchant,
            amount=Decimal("200.00"),
            currency="CNY",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("2.00"),
            settle_amount=Decimal("198.00"),
            status=PaymentOrder.OrderStatus.PENDING_REVIEW,
            agent_review_status=PaymentOrder.AgentReviewStatus.APPROVED,
            pay_method="WIRE_TRANSFER",
            beneficiary_name="Ready Co",
            expire_at=expire,
        )
        self.user = SystemUser.objects.create(
            username="ops_agent_queue",
            password_hash="x",
            real_name="Ops",
        )
        role = Role.objects.create(code="super_admin", name="Ops Super Admin Queue")
        UserRole.objects.create(user=self.user, role=role)
        self.factory = APIRequestFactory()

    def test_ops_list_excludes_pending_agent_review(self):
        request = self.factory.get("/api/v1/admin/orders/")
        force_authenticate(request, user=self.user)
        response = PaymentOrderViewSet.as_view({"get": "list"})(request)
        self.assertEqual(response.status_code, 200)
        nos = [row["order_no"] for row in response.data["results"]]
        self.assertIn("RMT_OPS_READY", nos)
        self.assertNotIn("RMT_AGENT_WAIT", nos)

    def test_ops_retrieve_can_see_pending_agent_review(self):
        request = self.factory.get("/api/v1/admin/orders/RMT_AGENT_WAIT/")
        force_authenticate(request, user=self.user)
        response = PaymentOrderViewSet.as_view({"get": "retrieve"})(
            request, order_no="RMT_AGENT_WAIT",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], PaymentOrder.OrderStatus.PENDING_AGENT_REVIEW)

    def test_ops_explicit_status_filter_can_list_agent_queue(self):
        request = self.factory.get(
            "/api/v1/admin/orders/",
            {"status": PaymentOrder.OrderStatus.PENDING_AGENT_REVIEW},
        )
        force_authenticate(request, user=self.user)
        response = PaymentOrderViewSet.as_view({"get": "list"})(request)
        self.assertEqual(response.status_code, 200)
        nos = [row["order_no"] for row in response.data["results"]]
        self.assertIn("RMT_AGENT_WAIT", nos)
        self.assertNotIn("RMT_OPS_READY", nos)


class AgentRemittancePortalApiTests(TestCase):
    def setUp(self):
        self.svc = UserService()
        self.svc.register(phone="13900000071", password="Test@123", sms_code="")
        self.user = EndUser.objects.get(phone="13900000071")
        self.svc.choose_role(self.user, "agent")
        self.user.refresh_from_db()
        self.svc.submit_onboarding(self.user, ONBOARDING_PAYLOAD)
        self.svc.review_onboarding(self.user, action="approve", reviewer="ops")
        self.user.refresh_from_db()
        self.merchant = create_eligible_merchant("AP")
        self.merchant.agent = self.user.default_agent
        self.merchant.save(update_fields=["agent", "updated_at"])
        expire = timezone.now() + timedelta(days=7)
        self.order = PaymentOrder.objects.create(
            order_no="RMT_PORTAL_WAIT",
            merchant_order_no="M_PORTAL_WAIT",
            unique_identification_no="UIN_PORTAL_WAIT",
            idempotency_key="IDEM_PORTAL_WAIT",
            merchant=self.merchant,
            amount=Decimal("300.00"),
            currency="CNY",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("3.00"),
            settle_amount=Decimal("297.00"),
            status=PaymentOrder.OrderStatus.PENDING_AGENT_REVIEW,
            agent_review_status=PaymentOrder.AgentReviewStatus.PENDING,
            pay_method="WIRE_TRANSFER",
            beneficiary_name="Portal Co",
            expire_at=expire,
        )
        self.client = APIClient()
        token = UserService._generate_token(str(self.user.id), user_type="user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_agent_can_list_view_and_agree(self):
        listed = self.client.get("/api/v1/user/agent/orders/", {"stage": "needs_review"})
        self.assertEqual(listed.status_code, 200)
        nos = [row["order_no"] for row in listed.data["items"]]
        self.assertIn(self.order.order_no, nos)
        detail = self.client.get(f"/api/v1/user/agent/orders/{self.order.order_no}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["beneficiary_name"], "Portal Co")
        reviewed = self.client.post(
            f"/api/v1/user/agent/orders/{self.order.order_no}/review/",
            {"action": "agree"},
            format="json",
        )
        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(reviewed.data["status"], PaymentOrder.OrderStatus.PENDING_REVIEW)
        self.assertEqual(reviewed.data["agent_review_status"], PaymentOrder.AgentReviewStatus.APPROVED)
        empty = self.client.get("/api/v1/user/agent/orders/", {"stage": "needs_review"})
        self.assertNotIn(self.order.order_no, [row["order_no"] for row in empty.data["items"]])
        agreed = self.client.get("/api/v1/user/agent/orders/", {"stage": "agreed"})
        self.assertIn(self.order.order_no, [row["order_no"] for row in agreed.data["items"]])
        all_orders = self.client.get("/api/v1/user/agent/orders/", {"stage": "all"})
        self.assertEqual(all_orders.status_code, 200)
        self.assertIn(self.order.order_no, [row["order_no"] for row in all_orders.data["items"]])
        self.assertGreaterEqual(all_orders.data["stats"]["total"], 1)

    def test_agent_lists_all_customer_orders_including_proxy(self):
        """Agent-proxy remittances skip agent review (status=none) but still appear under stage=all."""
        expire = timezone.now() + timedelta(days=7)
        proxy = PaymentOrder.objects.create(
            order_no="RMT_PORTAL_PROXY",
            merchant_order_no="M_PORTAL_PROXY",
            unique_identification_no="UIN_PORTAL_PROXY",
            idempotency_key="IDEM_PORTAL_PROXY",
            merchant=self.merchant,
            amount=Decimal("150.00"),
            currency="CNY",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("1.50"),
            settle_amount=Decimal("148.50"),
            status=PaymentOrder.OrderStatus.PENDING_REVIEW,
            agent_review_status=PaymentOrder.AgentReviewStatus.NONE,
            pay_method="WIRE_TRANSFER",
            beneficiary_name="Proxy Co",
            expire_at=expire,
        )
        needs = self.client.get("/api/v1/user/agent/orders/", {"stage": "needs_review"})
        self.assertNotIn(proxy.order_no, [row["order_no"] for row in needs.data["items"]])
        all_orders = self.client.get("/api/v1/user/agent/orders/", {"stage": "all"})
        nos = [row["order_no"] for row in all_orders.data["items"]]
        self.assertIn(self.order.order_no, nos)
        self.assertIn(proxy.order_no, nos)

    def test_other_agent_cannot_review(self):
        self.svc.register(phone="13900000072", password="Test@123", sms_code="")
        other_user = EndUser.objects.get(phone="13900000072")
        self.svc.choose_role(other_user, "agent")
        other_user.refresh_from_db()
        payload = {
            **ONBOARDING_PAYLOAD,
            "basic": {**ONBOARDING_PAYLOAD["basic"], "contact_phone": "13900000072"},
        }
        self.svc.submit_onboarding(other_user, payload)
        self.svc.review_onboarding(other_user, action="approve", reviewer="ops")
        other_user.refresh_from_db()
        self.assertNotEqual(other_user.default_agent_id, self.user.default_agent_id)
        token = UserService._generate_token(str(other_user.id), user_type="user")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        res = client.post(
            f"/api/v1/user/agent/orders/{self.order.order_no}/review/",
            {"action": "agree"},
            format="json",
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], "AGENT_ORDER_FORBIDDEN")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, PaymentOrder.OrderStatus.PENDING_AGENT_REVIEW)

    def test_customer_cannot_use_agent_order_api(self):
        self.svc.register(phone="13900000073", password="Test@123", sms_code="")
        customer = EndUser.objects.get(phone="13900000073")
        self.svc.choose_role(customer, "customer")
        token = UserService._generate_token(str(customer.id), user_type="user")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        res = client.get("/api/v1/user/agent/orders/")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], "NOT_AGENT")
