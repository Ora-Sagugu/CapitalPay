"""Agent payout-request gate is retired; merchant and agent books go to ops directly."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from apps.agent.models import Agent, AgentCustomer
from apps.core.exceptions import BusinessException
from apps.payment.models import PaymentOrder
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
from apps.user_portal.tests import ONBOARDING_PAYLOAD, ops_approve_onboarding


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

    def test_confirm_payment_does_not_arm_payout_request(self):
        order = self._order()
        confirmed = PaymentConfirmService().manual_confirm_by_order_no(order.order_no)
        self.assertEqual(confirmed.status, PaymentOrder.OrderStatus.PAY_RECEIVED)
        self.assertEqual(
            confirmed.agent_payout_request_status,
            PaymentOrder.AgentPayoutRequestStatus.NONE,
        )
        hop = resolve_next_hop(confirmed)
        self.assertNotEqual(hop, AWAITING_AGENT_PAYOUT_HOP)
        assert_confirm_transfer_allowed(confirmed)

    def test_request_payout_is_not_required(self):
        order = self._order()
        with self.assertRaises(BusinessException) as ctx:
            RemittanceApplicationService().request_payout_by_agent(order, reviewer="agent-1")
        self.assertEqual(ctx.exception.code, "AGENT_PAYOUT_REQUEST_NOT_REQUIRED")

    def test_legacy_merchant_agent_fk_skips_payout_gate(self):
        order = self._order()
        PaymentConfirmService().manual_confirm_by_order_no(order.order_no)
        order.refresh_from_db()
        self.assertEqual(
            order.agent_payout_request_status,
            PaymentOrder.AgentPayoutRequestStatus.NONE,
        )
        assert_confirm_transfer_allowed(order)

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
            account_number="6200030000000001",
            fee_rate=Decimal("0.002"),
            min_fee=Decimal("1.00"),
            max_fee=Decimal("500.00"),
            currency="USD",
            balance=Decimal("500.00"),
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

    def test_confirm_transfer_from_pending_pay_without_agent_gate(self):
        response = self._call("post", "confirm_transfer", self.pending_pay.order_no)
        self.assertEqual(response.status_code, 200, getattr(response, "data", response))
        self.pending_pay.refresh_from_db()
        self.assertEqual(self.pending_pay.status, PaymentOrder.OrderStatus.PENDING_SETTLE)

    def test_confirm_transfer_after_collection_without_payout_request(self):
        credited = self._call("post", "confirm_payment", self.pending_pay.order_no)
        self.assertEqual(credited.status_code, 200, getattr(credited, "data", credited))
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
            account_number="6200030000000002",
            fee_rate=Decimal("0.002"),
            min_fee=Decimal("1.00"),
            max_fee=Decimal("500.00"),
            currency="USD",
            balance=Decimal("500.00"),
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
        ops_approve_onboarding(self.svc, self.user)
        self.user.refresh_from_db()
        self.customer = AgentCustomer.objects.create(
            agent=self.user.default_agent,
            legal_name="Payout Customer",
            kyc_status=AgentCustomer.KycStatus.APPROVED,
        )
        expire = _expire()
        self.collected = PaymentOrder.objects.create(
            order_no="RMT_PORTAL_PAYOUT",
            merchant_order_no="M_PORTAL_PAYOUT",
            unique_identification_no="UIN_PORTAL_PAYOUT",
            idempotency_key="IDEM_PORTAL_PAYOUT",
            merchant=None,
            agent=self.user.default_agent,
            agent_customer=self.customer,
            amount=Decimal("80.00"),
            currency="USD",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("1.00"),
            settle_amount=Decimal("79.00"),
            status=PaymentOrder.OrderStatus.PAY_RECEIVED,
            agent_payout_request_status=PaymentOrder.AgentPayoutRequestStatus.NONE,
            pay_method="WIRE_TRANSFER",
            pay_received_at=timezone.now(),
            expire_at=expire,
        )
        self.client = APIClient()
        token = UserService._generate_token(str(self.user.id), user_type="user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_agent_payout_request_endpoint_is_disabled(self):
        listed = self.client.get("/api/v1/user/agent/orders/", {"stage": "awaiting_payout"})
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.data["items"], [])
        self.assertEqual(listed.data["stats"]["awaiting_payout"], 0)

        first = self.client.post(
            f"/api/v1/user/agent/orders/{self.collected.order_no}/request-payout/",
            {},
            format="json",
        )
        self.assertEqual(first.status_code, 409)
        self.assertEqual(first.data["code"], "AGENT_PAYOUT_REQUEST_NOT_REQUIRED")

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
        ops_approve_onboarding(self.svc, other_user)
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
