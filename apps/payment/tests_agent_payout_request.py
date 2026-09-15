"""Agent must request payout after collection before ops Confirm transfer."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from apps.agent.models import Agent
from apps.core.exceptions import BusinessException
from apps.payment.models import PaymentOrder
from apps.payment.serializers import build_order_timeline
from apps.payment.services.fund_trace import AWAITING_AGENT_PAYOUT_HOP, resolve_next_hop
from apps.payment.services.payment import PaymentConfirmService
from apps.payment.services.remittance_application import (
    RemittanceApplicationService,
    assert_confirm_transfer_allowed,
)
from apps.payment.tests_remittance_v2 import create_eligible_merchant
from apps.payment.views import PaymentOrderViewSet
from apps.rbac.models import SystemUser
from apps.rbac.testing import attach_super_admin
from apps.routing.models import BankChannel
from apps.user_portal.models import EndUser
from apps.user_portal.services import UserService
from apps.user_portal.tests import ONBOARDING_PAYLOAD


def _expire():
    return timezone.now() + timedelta(days=7)


class AgentPayoutRequestServiceTests(TestCase):
    def setUp(self):
        self.merchant = create_eligible_merchant("PR")
        self.agent = Agent.objects.create(
            agent_no="AG_PAYOUT_01",
            agent_name="Payout Agent",
            status="ACTIVE",
        )
        self.merchant.agent = self.agent
        self.merchant.save(update_fields=["agent", "updated_at"])

    def _order(self, **kwargs):
        suffix = timezone.now().strftime("%H%M%S%f")
        values = {
            "order_no": f"RMT_PR_{suffix}",
            "merchant_order_no": f"M_PR_{suffix}",
            "unique_identification_no": f"UIN_PR_{suffix}",
            "idempotency_key": f"IDEM_PR_{suffix}",
            "merchant": self.merchant,
            "amount": Decimal("100.00"),
            "sender_total_amount": Decimal("100.00"),
            "currency": "USD",
            "from_currency": "USD",
            "to_currency": "CNY",
            "fee_amount": Decimal("1.00"),
            "settle_amount": Decimal("99.00"),
            "status": PaymentOrder.OrderStatus.PENDING_PAY,
            "pay_method": "WIRE_TRANSFER",
            "expire_at": _expire(),
        }
        values.update(kwargs)
        return PaymentOrder.objects.create(**values)

    def test_confirm_payment_arms_pending_payout_request(self):
        order = self._order()
        confirmed = PaymentConfirmService().manual_confirm_by_order_no(order.order_no)
        self.assertEqual(confirmed.status, PaymentOrder.OrderStatus.PAY_RECEIVED)
        self.assertEqual(
            confirmed.agent_payout_request_status,
            PaymentOrder.AgentPayoutRequestStatus.PENDING,
        )
        hop = resolve_next_hop(confirmed)
        self.assertEqual(hop, AWAITING_AGENT_PAYOUT_HOP)
        steps = {step["code"]: step for step in build_order_timeline(confirmed)}
        self.assertIn("agent_payout_request", steps)
        self.assertTrue(steps["agent_payout_request"]["active"])
        self.assertFalse(steps["settlement"]["active"])

    def test_cannot_request_payout_before_collection(self):
        order = self._order()
        with self.assertRaises(BusinessException) as ctx:
            RemittanceApplicationService().request_payout_by_agent(order, reviewer="agent-1")
        self.assertEqual(ctx.exception.code, "AGENT_PAYOUT_STATUS_INVALID")

    def test_request_payout_is_idempotent_and_unlocks_confirm_transfer(self):
        order = self._order()
        PaymentConfirmService().manual_confirm_by_order_no(order.order_no)
        order.refresh_from_db()
        with self.assertRaises(BusinessException) as blocked:
            assert_confirm_transfer_allowed(order)
        self.assertEqual(blocked.exception.code, "AGENT_PAYOUT_REQUEST_REQUIRED")

        first = RemittanceApplicationService().request_payout_by_agent(order, reviewer="agent-1")
        self.assertEqual(
            first.agent_payout_request_status,
            PaymentOrder.AgentPayoutRequestStatus.REQUESTED,
        )
        self.assertEqual(first.agent_payout_requested_by, "agent-1")
        second = RemittanceApplicationService().request_payout_by_agent(order, reviewer="agent-2")
        self.assertEqual(second.agent_payout_requested_by, "agent-1")
        assert_confirm_transfer_allowed(second)
        steps = {step["code"]: step for step in build_order_timeline(second)}
        self.assertTrue(steps["agent_payout_request"]["verified"])
        self.assertTrue(steps["settlement"]["active"])

    def test_direct_customer_skips_payout_gate(self):
        self.merchant.agent = None
        self.merchant.save(update_fields=["agent", "updated_at"])
        order = self._order()
        PaymentConfirmService().manual_confirm_by_order_no(order.order_no)
        order.refresh_from_db()
        self.assertEqual(
            order.agent_payout_request_status,
            PaymentOrder.AgentPayoutRequestStatus.NONE,
        )
        assert_confirm_transfer_allowed(order)
        with self.assertRaises(BusinessException) as ctx:
            RemittanceApplicationService().request_payout_by_agent(order, reviewer="nobody")
        self.assertEqual(ctx.exception.code, "AGENT_PAYOUT_REQUEST_NOT_REQUIRED")

    @override_settings(ENABLE_AGENTS=False)
    def test_agents_disabled_skips_payout_gate(self):
        order = self._order()
        PaymentConfirmService().manual_confirm_by_order_no(order.order_no)
        order.refresh_from_db()
        self.assertEqual(
            order.agent_payout_request_status,
            PaymentOrder.AgentPayoutRequestStatus.NONE,
        )
        assert_confirm_transfer_allowed(order)


class AgentPayoutRequestOpsApiTests(TestCase):
    def setUp(self):
        self.merchant = create_eligible_merchant("PO")
        self.agent = Agent.objects.create(
            agent_no="AG_PAYOUT_OPS",
            agent_name="Ops Payout Agent",
            status="ACTIVE",
        )
        self.merchant.agent = self.agent
        self.merchant.save(update_fields=["agent", "updated_at"])
        expire = _expire()
        self.pending_pay = PaymentOrder.objects.create(
            order_no="RMT_PAYOUT_GATE_PAY",
            merchant_order_no="M_PAYOUT_GATE_PAY",
            unique_identification_no="UIN_PAYOUT_GATE_PAY",
            idempotency_key="IDEM_PAYOUT_GATE_PAY",
            merchant=self.merchant,
            amount=Decimal("100.00"),
            sender_total_amount=Decimal("100.00"),
            currency="USD",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("1.00"),
            settle_amount=Decimal("99.00"),
            status=PaymentOrder.OrderStatus.PENDING_PAY,
            pay_method="WIRE_TRANSFER",
            expire_at=expire,
        )
        BankChannel.objects.create(
            bank_code="MID",
            bank_name="Mid Bank",
            fee_rate=Decimal("0.002"),
            min_fee=Decimal("1.00"),
            max_fee=Decimal("500.00"),
            usd_balance=Decimal("500.00"),
            priority=1,
        )
        self.ops = SystemUser.objects.create(
            username="ops_payout_gate",
            password_hash="x",
            real_name="Ops",
        )
        attach_super_admin(self.ops)
        self.factory = APIRequestFactory()

    def _call(self, method, action, order_no, data=None):
        path = f"/api/v1/admin/orders/{order_no}/{action.replace('_', '-')}/"
        if method == "get":
            request = self.factory.get(path)
        else:
            request = self.factory.post(path, data or {}, format="json")
        force_authenticate(request, user=self.ops)
        return PaymentOrderViewSet.as_view({method: action})(request, order_no=order_no)

    def test_confirm_transfer_blocked_on_pending_pay_for_bound_agent(self):
        response = self._call("post", "confirm_transfer", self.pending_pay.order_no)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "AGENT_PAYOUT_REQUEST_REQUIRED")
        self.pending_pay.refresh_from_db()
        self.assertEqual(self.pending_pay.status, PaymentOrder.OrderStatus.PENDING_PAY)
        self.assertFalse(self.pending_pay.bank_code)

    def test_confirm_transfer_blocked_until_agent_requests(self):
        credited = self._call("post", "confirm_payment", self.pending_pay.order_no)
        self.assertEqual(credited.status_code, 200, getattr(credited, "data", credited))
        blocked = self._call("post", "confirm_transfer", self.pending_pay.order_no)
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.data["code"], "AGENT_PAYOUT_REQUEST_REQUIRED")

        self.pending_pay.refresh_from_db()
        RemittanceApplicationService().request_payout_by_agent(
            self.pending_pay, reviewer="agent-ops",
        )
        transferred = self._call("post", "confirm_transfer", self.pending_pay.order_no)
        self.assertEqual(transferred.status_code, 200, getattr(transferred, "data", transferred))
        self.pending_pay.refresh_from_db()
        self.assertEqual(self.pending_pay.status, PaymentOrder.OrderStatus.PENDING_SETTLE)


class DirectCustomerPayoutStillOpenTests(TestCase):
    def setUp(self):
        self.merchant = create_eligible_merchant("PD")
        expire = _expire()
        self.ready = PaymentOrder.objects.create(
            order_no="RMT_DIRECT_PAYOUT",
            merchant_order_no="M_DIRECT_PAYOUT",
            unique_identification_no="UIN_DIRECT_PAYOUT",
            idempotency_key="IDEM_DIRECT_PAYOUT",
            merchant=self.merchant,
            amount=Decimal("100.00"),
            sender_total_amount=Decimal("100.00"),
            currency="USD",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("1.00"),
            settle_amount=Decimal("99.00"),
            status=PaymentOrder.OrderStatus.PENDING_PAY,
            pay_method="WIRE_TRANSFER",
            expire_at=expire,
        )
        BankChannel.objects.create(
            bank_code="MID",
            bank_name="Mid Bank",
            fee_rate=Decimal("0.002"),
            min_fee=Decimal("1.00"),
            max_fee=Decimal("500.00"),
            usd_balance=Decimal("500.00"),
            priority=1,
        )
        self.ops = SystemUser.objects.create(
            username="ops_direct_payout",
            password_hash="x",
            real_name="Ops",
        )
        attach_super_admin(self.ops)
        self.factory = APIRequestFactory()

    def test_direct_customer_confirm_transfer_from_pending_pay(self):
        path = f"/api/v1/admin/orders/{self.ready.order_no}/confirm-transfer/"
        request = self.factory.post(path, {}, format="json")
        force_authenticate(request, user=self.ops)
        response = PaymentOrderViewSet.as_view({"post": "confirm_transfer"})(
            request, order_no=self.ready.order_no,
        )
        self.assertEqual(response.status_code, 200, getattr(response, "data", response))
        self.ready.refresh_from_db()
        self.assertEqual(self.ready.status, PaymentOrder.OrderStatus.PENDING_SETTLE)


class AgentPayoutRequestPortalApiTests(TestCase):
    def setUp(self):
        self.svc = UserService()
        self.svc.register(phone="13900000081", password="Test@123", sms_code="")
        self.user = EndUser.objects.get(phone="13900000081")
        self.svc.choose_role(self.user, "agent")
        self.user.refresh_from_db()
        payload = {
            **ONBOARDING_PAYLOAD,
            "basic": {**ONBOARDING_PAYLOAD["basic"], "contact_phone": "13900000081"},
        }
        self.svc.submit_onboarding(self.user, payload)
        self.svc.review_onboarding(self.user, action="approve", reviewer="ops")
        self.user.refresh_from_db()
        self.merchant = create_eligible_merchant("PP")
        self.merchant.agent = self.user.default_agent
        self.merchant.save(update_fields=["agent", "updated_at"])
        expire = _expire()
        self.collected = PaymentOrder.objects.create(
            order_no="RMT_PORTAL_PAYOUT",
            merchant_order_no="M_PORTAL_PAYOUT",
            unique_identification_no="UIN_PORTAL_PAYOUT",
            idempotency_key="IDEM_PORTAL_PAYOUT",
            merchant=self.merchant,
            amount=Decimal("80.00"),
            currency="USD",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("1.00"),
            settle_amount=Decimal("79.00"),
            status=PaymentOrder.OrderStatus.PAY_RECEIVED,
            agent_payout_request_status=PaymentOrder.AgentPayoutRequestStatus.PENDING,
            pay_method="WIRE_TRANSFER",
            pay_received_at=timezone.now(),
            expire_at=expire,
        )
        self.client = APIClient()
        token = UserService._generate_token(str(self.user.id), user_type="user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_agent_can_list_and_request_payout(self):
        listed = self.client.get("/api/v1/user/agent/orders/", {"stage": "awaiting_payout"})
        self.assertEqual(listed.status_code, 200)
        nos = [row["order_no"] for row in listed.data["items"]]
        self.assertIn(self.collected.order_no, nos)
        self.assertGreaterEqual(listed.data["stats"]["awaiting_payout"], 1)

        first = self.client.post(
            f"/api/v1/user/agent/orders/{self.collected.order_no}/request-payout/",
            {},
            format="json",
        )
        self.assertEqual(first.status_code, 200, getattr(first, "data", first))
        self.assertEqual(
            first.data["agent_payout_request_status"],
            PaymentOrder.AgentPayoutRequestStatus.REQUESTED,
        )
        second = self.client.post(
            f"/api/v1/user/agent/orders/{self.collected.order_no}/request-payout/",
            {},
            format="json",
        )
        self.assertEqual(second.status_code, 200)
        empty = self.client.get("/api/v1/user/agent/orders/", {"stage": "awaiting_payout"})
        self.assertNotIn(
            self.collected.order_no,
            [row["order_no"] for row in empty.data["items"]],
        )

    def test_other_agent_cannot_request_payout(self):
        self.svc.register(phone="13900000082", password="Test@123", sms_code="")
        other_user = EndUser.objects.get(phone="13900000082")
        self.svc.choose_role(other_user, "agent")
        other_user.refresh_from_db()
        payload = {
            **ONBOARDING_PAYLOAD,
            "basic": {**ONBOARDING_PAYLOAD["basic"], "contact_phone": "13900000082"},
        }
        self.svc.submit_onboarding(other_user, payload)
        self.svc.review_onboarding(other_user, action="approve", reviewer="ops")
        other_user.refresh_from_db()
        token = UserService._generate_token(str(other_user.id), user_type="user")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        res = client.post(
            f"/api/v1/user/agent/orders/{self.collected.order_no}/request-payout/",
            {},
            format="json",
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], "AGENT_ORDER_FORBIDDEN")
        self.collected.refresh_from_db()
        self.assertEqual(
            self.collected.agent_payout_request_status,
            PaymentOrder.AgentPayoutRequestStatus.PENDING,
        )
