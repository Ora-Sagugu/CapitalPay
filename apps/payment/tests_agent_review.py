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
from apps.user_portal.tests import ONBOARDING_PAYLOAD, ops_approve_onboarding


class AgentRemittanceReviewServiceTests(TestCase):
    def setUp(self):
        from apps.payment.tests_remittance_v2 import create_approved_customer

        self.merchant = create_eligible_merchant("AR")
        self.customer = create_approved_customer(self.merchant)
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
            agent_customer=self.customer if actor_type == "CUSTOMER" else None,
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
            agent_customer=self.customer if actor_type == "CUSTOMER" else None,
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

    def test_submit_with_agent_still_goes_pending_review(self):
        self.merchant.agent = self.agent
        self.merchant.save(update_fields=["agent", "updated_at"])
        order, created = self.submit()
        self.assertTrue(created)
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PENDING_REVIEW)
        self.assertEqual(order.agent_review_status, PaymentOrder.AgentReviewStatus.NONE)
        timeline = build_order_timeline(order)
        codes = [step["code"] for step in timeline]
        self.assertNotIn("agent_review", codes)
        ops_step = next(step for step in timeline if step["code"] == "review")
        self.assertTrue(ops_step["active"])
        self.assertFalse(ops_step["verified"])

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

    def _legacy_agent_queue_order(self, *, key="idem-legacy"):
        expire = timezone.now() + timedelta(days=7)
        return PaymentOrder.objects.create(
            order_no=f"RMT_LEGACY_{key}",
            merchant_order_no=f"M_LEGACY_{key}",
            unique_identification_no=f"UIN_LEGACY_{key}",
            idempotency_key=f"IDEM_LEGACY_{key}",
            merchant=self.merchant,
            amount=Decimal("1000.00"),
            currency="USD",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("3.00"),
            settle_amount=Decimal("997.00"),
            status=PaymentOrder.OrderStatus.PENDING_AGENT_REVIEW,
            agent_review_status=PaymentOrder.AgentReviewStatus.PENDING,
            pay_method="WIRE_TRANSFER",
            expire_at=expire,
        )

    def test_agent_agree_sends_to_ops_without_prn(self):
        self.merchant.agent = self.agent
        self.merchant.save(update_fields=["agent", "updated_at"])
        order = self._legacy_agent_queue_order()
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
        order.status = PaymentOrder.OrderStatus.PENDING_AGENT_REVIEW
        order.agent_review_status = PaymentOrder.AgentReviewStatus.PENDING
        order.save(update_fields=["status", "agent_review_status", "updated_at"])
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
        order = self._legacy_agent_queue_order(key="reject-reason")
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
        ops_approve_onboarding(self.svc, self.user)
        self.user.refresh_from_db()
        from apps.agent.models import AgentCustomer
        self.customer = AgentCustomer.objects.create(
            agent=self.user.default_agent,
            legal_name="Portal Co",
            kyc_status=AgentCustomer.KycStatus.APPROVED,
        )
        expire = timezone.now() + timedelta(days=7)
        self.order = PaymentOrder.objects.create(
            order_no="RMT_PORTAL_WAIT",
            merchant_order_no="M_PORTAL_WAIT",
            unique_identification_no="UIN_PORTAL_WAIT",
            idempotency_key="IDEM_PORTAL_WAIT",
            merchant=None,
            agent=self.user.default_agent,
            agent_customer=self.customer,
            amount=Decimal("300.00"),
            currency="CNY",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("3.00"),
            settle_amount=Decimal("297.00"),
            status=PaymentOrder.OrderStatus.PENDING_REVIEW,
            agent_review_status=PaymentOrder.AgentReviewStatus.NONE,
            pay_method="WIRE_TRANSFER",
            beneficiary_name="Portal Co",
            expire_at=expire,
        )
        self.client = APIClient()
        token = UserService._generate_token(str(self.user.id), user_type="user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_agent_can_list_own_booked_orders(self):
        listed = self.client.get("/api/v1/user/agent/orders/", {"stage": "needs_review"})
        self.assertEqual(listed.status_code, 200)
        nos = [row["order_no"] for row in listed.data["items"]]
        self.assertIn(self.order.order_no, nos)
        detail = self.client.get(f"/api/v1/user/agent/orders/{self.order.order_no}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["beneficiary_name"], "Portal Co")
        all_orders = self.client.get("/api/v1/user/agent/orders/", {"stage": "all"})
        self.assertEqual(all_orders.status_code, 200)
        self.assertIn(self.order.order_no, [row["order_no"] for row in all_orders.data["items"]])
        self.assertGreaterEqual(all_orders.data["stats"]["total"], 1)

    def test_agent_order_earning_is_share_of_net_fee(self):
        from apps.settlement.engine.calculator import SettlementCalculator

        agent = self.user.default_agent
        agent.commission_rate = Decimal("0.500000")
        agent.save(update_fields=["commission_rate"])
        SettlementCalculator().calculate_fee_share(self.order, channel_rate=Decimal("0"))
        listed = self.client.get("/api/v1/user/agent/orders/", {"stage": "all"})
        self.assertEqual(listed.status_code, 200)
        row = next(item for item in listed.data["items"] if item["order_no"] == self.order.order_no)
        self.assertEqual(row["agent_fee"], "1.50")
        detail = self.client.get(f"/api/v1/user/agent/orders/{self.order.order_no}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["agent_fee"], "1.50")


    def test_agent_lists_all_booked_orders_including_later_statuses(self):
        expire = timezone.now() + timedelta(days=7)
        proxy = PaymentOrder.objects.create(
            order_no="RMT_PORTAL_PROXY",
            merchant_order_no="M_PORTAL_PROXY",
            unique_identification_no="UIN_PORTAL_PROXY",
            idempotency_key="IDEM_PORTAL_PROXY",
            merchant=None,
            agent=self.user.default_agent,
            agent_customer=self.customer,
            amount=Decimal("150.00"),
            currency="CNY",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("1.50"),
            settle_amount=Decimal("148.50"),
            status=PaymentOrder.OrderStatus.PENDING_PAY,
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
        ops_approve_onboarding(self.svc, other_user)
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
        self.assertEqual(self.order.status, PaymentOrder.OrderStatus.PENDING_REVIEW)

    def test_customer_cannot_use_agent_order_api(self):
        self.svc.register(phone="13900000073", password="Test@123", sms_code="")
        customer = EndUser.objects.get(phone="13900000073")
        self.svc.choose_role(customer, "merchant")
        token = UserService._generate_token(str(customer.id), user_type="user")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        res = client.get("/api/v1/user/agent/orders/")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], "NOT_AGENT")


class AgentBoundMerchantOrdersVisibilityTests(TestCase):
    """Bound agents can view merchant remittances but cannot operate on them."""

    def setUp(self):
        from apps.agent.models import AgentCustomer, AgentMerchant
        from apps.payment.tests_remittance_v2 import create_eligible_merchant

        self.svc = UserService()
        self.svc.register(phone="13900000081", password="Test@123", sms_code="")
        self.agent_user = EndUser.objects.get(phone="13900000081")
        self.svc.choose_role(self.agent_user, "agent")
        self.agent_user.refresh_from_db()
        self.svc.submit_onboarding(self.agent_user, {
            **ONBOARDING_PAYLOAD,
            "basic": {**ONBOARDING_PAYLOAD["basic"], "contact_phone": "13900000081"},
        })
        ops_approve_onboarding(self.svc, self.agent_user)
        self.agent_user.refresh_from_db()
        self.agent = self.agent_user.default_agent

        self.merchant = create_eligible_merchant("BM")
        self.merchant.agent = self.agent
        self.merchant.save(update_fields=["agent", "updated_at"])
        AgentMerchant.objects.update_or_create(
            agent=self.agent,
            merchant=self.merchant,
            defaults={
                "is_deleted": False,
                "effective_from": timezone.localdate(),
                "commission_rate": self.agent.commission_rate,
            },
        )
        self.customer = AgentCustomer.objects.create(
            merchant=self.merchant,
            agent=None,
            legal_name="Bound Merchant Customer",
            kyc_status=AgentCustomer.KycStatus.APPROVED,
        )
        unbound = create_eligible_merchant("UB")
        expire = timezone.now() + timedelta(days=7)
        self.bound_order = PaymentOrder.objects.create(
            order_no="RMT_BOUND_MERCHANT",
            merchant_order_no="M_BOUND_MERCHANT",
            unique_identification_no="UIN_BOUND_MERCHANT",
            idempotency_key="IDEM_BOUND_MERCHANT",
            merchant=self.merchant,
            agent=None,
            agent_customer=self.customer,
            amount=Decimal("500.00"),
            currency="CNY",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("5.00"),
            settle_amount=Decimal("495.00"),
            status=PaymentOrder.OrderStatus.PENDING_REVIEW,
            agent_review_status=PaymentOrder.AgentReviewStatus.NONE,
            pay_method="WIRE_TRANSFER",
            beneficiary_name="Supplier Bound",
            expire_at=expire,
        )
        self.unbound_order = PaymentOrder.objects.create(
            order_no="RMT_UNBOUND_MERCHANT",
            merchant_order_no="M_UNBOUND_MERCHANT",
            unique_identification_no="UIN_UNBOUND_MERCHANT",
            idempotency_key="IDEM_UNBOUND_MERCHANT",
            merchant=unbound,
            agent=None,
            amount=Decimal("200.00"),
            currency="CNY",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("2.00"),
            settle_amount=Decimal("198.00"),
            status=PaymentOrder.OrderStatus.PENDING_REVIEW,
            agent_review_status=PaymentOrder.AgentReviewStatus.NONE,
            pay_method="WIRE_TRANSFER",
            beneficiary_name="Supplier Unbound",
            expire_at=expire,
        )
        self.client = APIClient()
        token = UserService._generate_token(str(self.agent_user.id), user_type="user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_agent_lists_bound_merchant_remittances(self):
        listed = self.client.get("/api/v1/user/agent/orders/", {"stage": "all"})
        self.assertEqual(listed.status_code, 200)
        nos = [row["order_no"] for row in listed.data["items"]]
        self.assertIn(self.bound_order.order_no, nos)
        self.assertNotIn(self.unbound_order.order_no, nos)
        row = next(item for item in listed.data["items"] if item["order_no"] == self.bound_order.order_no)
        self.assertEqual(row["merchant_no"], self.merchant.merchant_no)
        self.assertEqual(row["merchant_name"], self.merchant.merchant_name)
        self.assertTrue(row["read_only"])

        detail = self.client.get(f"/api/v1/user/agent/orders/{self.bound_order.order_no}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["beneficiary_name"], "Supplier Bound")
        self.assertTrue(detail.data["read_only"])

    def test_bound_merchant_order_earning_uses_agent_share(self):
        from apps.settlement.engine.calculator import SettlementCalculator

        self.agent.commission_rate = Decimal("0.500000")
        self.agent.save(update_fields=["commission_rate"])
        SettlementCalculator().calculate_fee_share(self.bound_order, channel_rate=Decimal("0"))
        listed = self.client.get("/api/v1/user/agent/orders/", {"stage": "all"})
        row = next(item for item in listed.data["items"] if item["order_no"] == self.bound_order.order_no)
        self.assertEqual(row["agent_fee"], "2.50")


    def test_agent_cannot_operate_on_bound_merchant_remittances(self):
        review = self.client.post(
            f"/api/v1/user/agent/orders/{self.bound_order.order_no}/review/",
            {"action": "agree"},
            format="json",
        )
        self.assertEqual(review.status_code, 403)
        self.assertEqual(review.data["code"], "AGENT_ORDER_READ_ONLY")

        payout = self.client.post(
            f"/api/v1/user/agent/orders/{self.bound_order.order_no}/request-payout/",
            {},
            format="json",
        )
        self.assertEqual(payout.status_code, 403)
        self.assertEqual(payout.data["code"], "AGENT_ORDER_READ_ONLY")

        unbound_detail = self.client.get(f"/api/v1/user/agent/orders/{self.unbound_order.order_no}/")
        self.assertEqual(unbound_detail.status_code, 403)
        self.assertEqual(unbound_detail.data["code"], "AGENT_ORDER_FORBIDDEN")
