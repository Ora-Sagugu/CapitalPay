"""Banking Transfers queue: remittance orders awaiting Confirm transfer."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.payment.models import PaymentOrder
from apps.payment.tests_remittance_v2 import create_eligible_merchant
from apps.payment.views import PaymentOrderViewSet
from apps.rbac.models import Role, SystemUser, UserRole
from apps.rbac.services import AuthService
from apps.rbac.testing import attach_super_admin
from apps.routing.models import BankChannel


def _expire():
    return timezone.now() + timedelta(days=7)


class PendingTransfersQueueTests(TestCase):
    def setUp(self):
        self.merchant = create_eligible_merchant("PT")
        expire = _expire()
        self.review = self._order("REVIEW", PaymentOrder.OrderStatus.PENDING_REVIEW, expire)
        self.pending_pay = self._order("PAY", PaymentOrder.OrderStatus.PENDING_PAY, expire)
        self.pay_received = self._order(
            "RECV",
            PaymentOrder.OrderStatus.PAY_RECEIVED,
            expire,
            pay_received_at=timezone.now(),
        )
        self.awaiting_agent = self._order(
            "WAIT",
            PaymentOrder.OrderStatus.PAY_RECEIVED,
            expire,
            pay_received_at=timezone.now(),
            agent_payout_request_status=PaymentOrder.AgentPayoutRequestStatus.PENDING,
        )
        self.requested = self._order(
            "REQ",
            PaymentOrder.OrderStatus.PAY_RECEIVED,
            expire,
            pay_received_at=timezone.now(),
            agent_payout_request_status=PaymentOrder.AgentPayoutRequestStatus.REQUESTED,
        )
        self.settled = self._order("SETTLE", PaymentOrder.OrderStatus.PENDING_SETTLE, expire)
        BankChannel.objects.create(
            bank_code="MID",
            bank_name="Mid Bank",
            account_number="6200030000000099",
            fee_rate=Decimal("0.002"),
            min_fee=Decimal("1.00"),
            max_fee=Decimal("500.00"),
            currency="USD",
            balance=Decimal("5000.00"),
            priority=1,
        )
        self.ops = SystemUser.objects.create(
            username="ops_pending_xfer",
            password_hash="x",
            real_name="Ops",
        )
        attach_super_admin(self.ops)
        self.factory = APIRequestFactory()

    def _order(self, suffix, status, expire, **kwargs):
        values = {
            "order_no": f"RMT_PT_{suffix}",
            "merchant_order_no": f"M_PT_{suffix}",
            "unique_identification_no": f"UIN_PT_{suffix}",
            "idempotency_key": f"IDEM_PT_{suffix}",
            "merchant": self.merchant,
            "amount": Decimal("100.00"),
            "sender_total_amount": Decimal("100.00"),
            "currency": "USD",
            "from_currency": "USD",
            "to_currency": "CNY",
            "fee_amount": Decimal("1.00"),
            "settle_amount": Decimal("99.00"),
            "status": status,
            "pay_method": "WIRE_TRANSFER",
            "expire_at": expire,
            "beneficiary_name": f"Bene {suffix}",
        }
        values.update(kwargs)
        return PaymentOrder.objects.create(**values)

    def _list(self, user=None):
        request = self.factory.get("/api/v1/admin/orders/pending-transfers/")
        force_authenticate(request, user=user or self.ops)
        return PaymentOrderViewSet.as_view({"get": "pending_transfers"})(request)

    def _confirm(self, order_no, user=None):
        request = self.factory.post(
            f"/api/v1/admin/orders/{order_no}/confirm-transfer/",
            {"bank_code": "MID"},
            format="json",
        )
        force_authenticate(request, user=user or self.ops)
        return PaymentOrderViewSet.as_view({"post": "confirm_transfer"})(
            request, order_no=order_no,
        )

    def test_queue_only_includes_confirm_transfer_orders(self):
        response = self._list()
        self.assertEqual(response.status_code, 200, getattr(response, "data", response))
        nos = [row["order_no"] for row in response.data["results"]]
        self.assertIn("RMT_PT_PAY", nos)
        self.assertIn("RMT_PT_RECV", nos)
        self.assertIn("RMT_PT_REQ", nos)
        self.assertNotIn("RMT_PT_REVIEW", nos)
        self.assertNotIn("RMT_PT_WAIT", nos)
        self.assertNotIn("RMT_PT_SETTLE", nos)

    def test_confirmed_order_leaves_the_queue(self):
        confirmed = self._confirm(self.pending_pay.order_no)
        self.assertEqual(confirmed.status_code, 200, getattr(confirmed, "data", confirmed))
        nos = [row["order_no"] for row in self._list().data["results"]]
        self.assertNotIn("RMT_PT_PAY", nos)
        self.assertIn("RMT_PT_RECV", nos)


class PendingTransfersPermissionTests(TestCase):
    def setUp(self):
        self.svc = AuthService()
        self.svc.ensure_ops_rbac()
        self.merchant = create_eligible_merchant("PP")
        self.order = PaymentOrder.objects.create(
            order_no="RMT_PT_PERM",
            merchant_order_no="M_PT_PERM",
            unique_identification_no="UIN_PT_PERM",
            idempotency_key="IDEM_PT_PERM",
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
            expire_at=_expire(),
            beneficiary_name="Bene Perm",
        )
        BankChannel.objects.create(
            bank_code="MID",
            bank_name="Mid Bank",
            account_number="6200030000000098",
            fee_rate=Decimal("0.002"),
            min_fee=Decimal("1.00"),
            max_fee=Decimal("500.00"),
            currency="USD",
            balance=Decimal("5000.00"),
            priority=1,
        )
        self.factory = APIRequestFactory()

    def _user_with(self, username, codes):
        role = Role.objects.create(code=f"role_{username}", name=username)
        self.svc.set_role_capabilities(role, codes)
        user = SystemUser.objects.create(
            username=username, password_hash="x", real_name=username,
        )
        UserRole.objects.create(user=user, role=role)
        return user

    def _call(self, user, method, action, order_no=None):
        if action == "pending_transfers":
            request = self.factory.get("/api/v1/admin/orders/pending-transfers/")
            force_authenticate(request, user=user)
            return PaymentOrderViewSet.as_view({"get": action})(request)
        path = f"/api/v1/admin/orders/{order_no}/{action.replace('_', '-')}/"
        if method == "get":
            request = self.factory.get(path)
        else:
            request = self.factory.post(path, {"bank_code": "MID"}, format="json")
        force_authenticate(request, user=user)
        return PaymentOrderViewSet.as_view({method: action})(request, order_no=order_no)

    def test_fund_transfers_can_list_and_confirm(self):
        user = self._user_with("xfer_ops", ["feature:fund_transfers"])
        listed = self._call(user, "get", "pending_transfers")
        self.assertEqual(listed.status_code, 200, getattr(listed, "data", listed))
        nos = [row["order_no"] for row in listed.data["results"]]
        self.assertIn("RMT_PT_PERM", nos)
        banks = self._call(user, "get", "payout_banks", self.order.order_no)
        self.assertEqual(banks.status_code, 200, getattr(banks, "data", banks))
        confirmed = self._call(user, "post", "confirm_transfer", self.order.order_no)
        self.assertEqual(confirmed.status_code, 200, getattr(confirmed, "data", confirmed))

    def test_orders_view_cannot_use_transfer_queue(self):
        user = self._user_with("order_viewer", ["feature:orders"])
        listed = self._call(user, "get", "pending_transfers")
        self.assertEqual(listed.status_code, 403)
        denied = self._call(user, "post", "confirm_transfer", self.order.order_no)
        self.assertEqual(denied.status_code, 403)
