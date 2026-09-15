"""Payout bank ranking: lowest Fee Rule first, skip insufficient balances."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.core.exceptions import BusinessException
from apps.payment.models import PaymentOrder
from apps.payment.tests_remittance_v2 import create_eligible_merchant
from apps.payment.views import PaymentOrderViewSet
from apps.rbac.models import Role, SystemUser, UserRole
from apps.routing.models import BankChannel, RoutingLog
from apps.routing.services import RoutingService


class RankPayoutBanksTests(TestCase):
    def _channel(self, code, *, fee_rate, usd=0, hkd=0, cny=0, **kwargs):
        defaults = {
            "min_fee": Decimal("0.00"),
            "max_fee": Decimal("500.00"),
        }
        defaults.update(kwargs)
        return BankChannel.objects.create(
            bank_code=code,
            bank_name=f"{code} Bank",
            fee_rate=Decimal(str(fee_rate)),
            usd_balance=Decimal(str(usd)),
            hkd_balance=Decimal(str(hkd)),
            cny_balance=Decimal(str(cny)),
            **defaults,
        )

    def test_selects_lowest_fee_when_balance_covers(self):
        cheap = self._channel("CHEAP", fee_rate="0.001", usd=1000)
        self._channel("DEAR", fee_rate="0.010", usd=1000)
        selected = RoutingService.select_payout_bank(Decimal("100.00"), "USD")
        self.assertEqual(selected["bank_code"], cheap.bank_code)
        self.assertTrue(selected["recommended"])
        ranked = RoutingService.rank_payout_banks(Decimal("100.00"), "USD")
        self.assertEqual([row["bank_code"] for row in ranked], ["CHEAP", "DEAR"])

    def test_skips_cheapest_when_balance_insufficient(self):
        self._channel("CHEAP", fee_rate="0.001", usd=10)
        second = self._channel("MID", fee_rate="0.002", usd=500)
        self._channel("DEAR", fee_rate="0.010", usd=5000)
        selected = RoutingService.select_payout_bank(Decimal("100.00"), "USD")
        self.assertEqual(selected["bank_code"], second.bank_code)
        ranked = RoutingService.rank_payout_banks(Decimal("100.00"), "USD")
        self.assertFalse(ranked[0]["sufficient"])
        self.assertTrue(ranked[1]["recommended"])

    def test_all_insufficient_raises(self):
        self._channel("CHEAP", fee_rate="0.001", usd=1)
        self._channel("DEAR", fee_rate="0.002", usd=2)
        with self.assertRaises(BusinessException) as ctx:
            RoutingService.select_payout_bank(Decimal("100.00"), "USD")
        self.assertEqual(ctx.exception.code, "NO_PAYOUT_BANK")

    def test_explicit_insufficient_bank_is_rejected(self):
        self._channel("CHEAP", fee_rate="0.001", usd=1)
        self._channel("MID", fee_rate="0.002", usd=500)
        with self.assertRaises(BusinessException) as ctx:
            RoutingService.select_payout_bank(Decimal("100.00"), "USD", bank_code="CHEAP")
        self.assertEqual(ctx.exception.code, "PAYOUT_BANK_INSUFFICIENT")

    def test_unknown_bank_is_rejected(self):
        self._channel("MID", fee_rate="0.002", usd=500)
        with self.assertRaises(BusinessException) as ctx:
            RoutingService.select_payout_bank(Decimal("100.00"), "USD", bank_code="NOPE")
        self.assertEqual(ctx.exception.code, "PAYOUT_BANK_INVALID")

    def test_unsupported_currency_is_excluded(self):
        self._channel("EURONLY", fee_rate="0.001", usd=5000, supported_currencies=["EUR"])
        usd = self._channel("USDBNK", fee_rate="0.005", usd=5000, supported_currencies=["USD"])
        selected = RoutingService.select_payout_bank(Decimal("100.00"), "USD")
        self.assertEqual(selected["bank_code"], usd.bank_code)


class AgentPayoutApiTests(TestCase):
    def setUp(self):
        self.merchant = create_eligible_merchant("PW")
        expire = timezone.now() + timedelta(days=7)
        self.pending = PaymentOrder.objects.create(
            order_no="RMT_PAYOUT_WAIT",
            merchant_order_no="M_PAYOUT_WAIT",
            unique_identification_no="UIN_PAYOUT_WAIT",
            idempotency_key="IDEM_PAYOUT_WAIT",
            merchant=self.merchant,
            amount=Decimal("100.00"),
            sender_total_amount=Decimal("100.00"),
            currency="USD",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("1.00"),
            settle_amount=Decimal("99.00"),
            status=PaymentOrder.OrderStatus.PENDING_REVIEW,
            pay_method="WIRE_TRANSFER",
            expire_at=expire,
        )
        self.ready = PaymentOrder.objects.create(
            order_no="RMT_PAYOUT_READY",
            merchant_order_no="M_PAYOUT_READY",
            unique_identification_no="UIN_PAYOUT_READY",
            idempotency_key="IDEM_PAYOUT_READY",
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
            bank_code="CHEAP",
            bank_name="Cheap Bank",
            fee_rate=Decimal("0.001"),
            min_fee=Decimal("1.00"),
            max_fee=Decimal("500.00"),
            usd_balance=Decimal("10.00"),
            priority=1,
        )
        BankChannel.objects.create(
            bank_code="MID",
            bank_name="Mid Bank",
            fee_rate=Decimal("0.002"),
            min_fee=Decimal("1.00"),
            max_fee=Decimal("500.00"),
            usd_balance=Decimal("500.00"),
            priority=99,
        )
        self.user = SystemUser.objects.create(
            username="ops_payout",
            password_hash="x",
            real_name="Ops",
        )
        role = Role.objects.create(code="super_admin", name="Ops Super Admin Payout")
        UserRole.objects.create(user=self.user, role=role)
        self.factory = APIRequestFactory()

    def _call(self, method, action, order_no, data=None):
        path = f"/api/v1/admin/orders/{order_no}/{action.replace('_', '-')}/"
        if method == "get":
            request = self.factory.get(path)
        else:
            request = self.factory.post(path, data or {}, format="json")
        force_authenticate(request, user=self.user)
        return PaymentOrderViewSet.as_view({method: action})(request, order_no=order_no)

    def test_unapproved_order_cannot_confirm_transfer(self):
        response = self._call("post", "confirm_transfer", self.pending.order_no)
        self.assertEqual(response.status_code, 400)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, PaymentOrder.OrderStatus.PENDING_REVIEW)
        self.assertFalse(self.pending.bank_code)

    def test_approve_does_not_auto_assign_bank(self):
        response = self._call("post", "review_remittance", self.pending.order_no, {"action": "approve"})
        self.assertEqual(response.status_code, 200, getattr(response, "data", response))
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, PaymentOrder.OrderStatus.PENDING_PAY)
        self.assertFalse(self.pending.bank_code)

    def test_payout_banks_recommends_second_cheapest_with_balance(self):
        response = self._call("get", "payout_banks", self.ready.order_no)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["recommended_bank_code"], "MID")
        codes = [row["bank_code"] for row in response.data["results"]]
        self.assertEqual(codes, ["CHEAP", "MID"])
        cheap = response.data["results"][0]
        self.assertFalse(cheap["sufficient"])
        self.assertFalse(cheap["recommended"])

    def test_confirm_transfer_auto_selects_waterfall_bank(self):
        response = self._call("post", "confirm_transfer", self.ready.order_no)
        self.assertEqual(response.status_code, 200, getattr(response, "data", response))
        self.assertEqual(response.data["bank_code"], "MID")
        self.ready.refresh_from_db()
        self.assertEqual(self.ready.bank_code, "MID")
        self.assertEqual(self.ready.status, PaymentOrder.OrderStatus.PENDING_SETTLE)
        log = RoutingLog.objects.get(order_no=self.ready.order_no)
        self.assertEqual(log.request_data["skipped_cheaper_banks"][0]["bank_code"], "CHEAP")

    def test_confirm_transfer_rejects_insufficient_explicit_bank(self):
        response = self._call(
            "post", "confirm_transfer", self.ready.order_no, {"bank_code": "CHEAP"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "PAYOUT_BANK_INSUFFICIENT")
        self.ready.refresh_from_db()
        self.assertEqual(self.ready.status, PaymentOrder.OrderStatus.PENDING_PAY)
        self.assertFalse(self.ready.bank_code)
