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
    def _channel(self, code, *, fee_rate, balance=0, currency="USD", **kwargs):
        defaults = {
            "min_fee": Decimal("0.00"),
            "max_fee": Decimal("500.00"),
        }
        defaults.update(kwargs)
        return BankChannel.objects.create(
            bank_code=code,
            bank_name=f"{code} Bank",
            account_number=defaults.pop("account_number", f"62{''.join(str(ord(c) % 10) for c in code).ljust(14, '0')[:14]}"),
            fee_rate=Decimal(str(fee_rate)),
            currency=(currency or "USD").upper(),
            balance=Decimal(str(balance)),
            **defaults,
        )

    def test_selects_lowest_fee_when_balance_covers(self):
        cheap = self._channel("CHEAP", fee_rate="0.001", balance=1000)
        self._channel("DEAR", fee_rate="0.010", balance=1000)
        selected = RoutingService.select_payout_bank(Decimal("100.00"), "USD")
        self.assertEqual(selected["bank_code"], cheap.bank_code)
        self.assertTrue(selected["recommended"])
        ranked = RoutingService.rank_payout_banks(Decimal("100.00"), "USD")
        self.assertEqual([row["bank_code"] for row in ranked], ["CHEAP", "DEAR"])

    def test_channel_fee_clamps_to_max_fee(self):
        channel = self._channel(
            "CAP08",
            fee_rate="0.0008",
            max_fee="20.00",
            balance=1_000_000,
        )
        # 100_000 * 0.08% = 80, capped at 20
        self.assertEqual(
            RoutingService._channel_fee(channel, Decimal("100000.00")),
            Decimal("20.00"),
        )
        # 1_000 * 0.08% = 0.80, below max
        self.assertEqual(
            RoutingService._channel_fee(channel, Decimal("1000.00")),
            Decimal("0.80"),
        )

    def test_skips_cheapest_when_balance_insufficient(self):
        cheap = self._channel("CHEAP", fee_rate="0.001", balance=10)
        second = self._channel("MID", fee_rate="0.002", balance=500)
        self._channel("DEAR", fee_rate="0.010", balance=5000)
        selected = RoutingService.select_payout_bank(Decimal("100.00"), "USD")
        self.assertEqual(selected["bank_code"], cheap.bank_code)
        self.assertEqual(
            [(leg["bank_code"], leg["amount"]) for leg in selected["splits"]],
            [("CHEAP", "10.00"), ("MID", "90.00")],
        )
        ranked = RoutingService.rank_payout_banks(Decimal("100.00"), "USD")
        self.assertFalse(ranked[0]["sufficient"])
        self.assertTrue(ranked[0]["partial"])
        self.assertTrue(ranked[0]["recommended"])
        self.assertTrue(ranked[1]["recommended"])
        self.assertEqual(ranked[1]["bank_code"], second.bank_code)

    def test_skips_bank_when_fee_not_below_remittance_fee(self):
        dear = self._channel("DEAR", fee_rate="0.050", balance=5000)  # 5.00 on 100
        cheap = self._channel("CHEAP", fee_rate="0.001", balance=5000)  # 0.10 on 100
        ranked = RoutingService.rank_payout_banks(
            Decimal("100.00"), "USD", remittance_fee=Decimal("1.00"),
        )
        dear_row = next(row for row in ranked if row["bank_code"] == dear.bank_code)
        cheap_row = next(row for row in ranked if row["bank_code"] == cheap.bank_code)
        self.assertFalse(dear_row["bank_fee_ok"])
        self.assertFalse(dear_row["selectable"])
        self.assertTrue(cheap_row["bank_fee_ok"])
        self.assertTrue(cheap_row["recommended"])
        with self.assertRaises(BusinessException) as ctx:
            RoutingService.select_payout_bank(
                Decimal("100.00"), "USD", bank_code="DEAR", remittance_fee=Decimal("1.00"),
            )
        self.assertEqual(ctx.exception.code, "PAYOUT_BANK_FEE_EXCEEDS")

    def test_all_insufficient_raises(self):
        self._channel("CHEAP", fee_rate="0.001", balance=1)
        self._channel("DEAR", fee_rate="0.002", balance=2)
        with self.assertRaises(BusinessException) as ctx:
            RoutingService.select_payout_bank(Decimal("100.00"), "USD")
        self.assertEqual(ctx.exception.code, "NO_PAYOUT_BANK")

    def test_split_rejected_when_both_banks_cover_the_payout(self):
        self._channel("CHEAP", fee_rate="0.001", balance=500)
        self._channel("MID", fee_rate="0.002", balance=500)
        with self.assertRaises(BusinessException) as ctx:
            RoutingService.select_payout_bank(
                Decimal("100.00"), "USD", bank_codes=["CHEAP", "MID"],
            )
        self.assertEqual(ctx.exception.code, "PAYOUT_BANK_SPLIT_INVALID")

    def test_explicit_split_uses_remaining_then_second_bank(self):
        cheap = self._channel("CHEAP", fee_rate="0.001", balance=20)
        mid = self._channel("MID", fee_rate="0.002", balance=500)
        selected = RoutingService.select_payout_bank(
            Decimal("100.00"), "USD", bank_codes=["MID", "CHEAP"],
        )
        self.assertEqual(selected["bank_code"], cheap.bank_code)
        self.assertEqual(selected["splits"][0]["amount"], "20.00")
        self.assertEqual(selected["splits"][1]["bank_code"], mid.bank_code)
        self.assertEqual(selected["splits"][1]["amount"], "80.00")
        self.assertEqual(selected["computed_fee"], "0.18")

    def test_explicit_insufficient_bank_is_rejected(self):
        self._channel("CHEAP", fee_rate="0.001", balance=1)
        self._channel("MID", fee_rate="0.002", balance=500)
        with self.assertRaises(BusinessException) as ctx:
            RoutingService.select_payout_bank(Decimal("100.00"), "USD", bank_code="CHEAP")
        self.assertEqual(ctx.exception.code, "PAYOUT_BANK_INSUFFICIENT")

    def test_unknown_bank_is_rejected(self):
        self._channel("MID", fee_rate="0.002", balance=500)
        with self.assertRaises(BusinessException) as ctx:
            RoutingService.select_payout_bank(Decimal("100.00"), "USD", bank_code="NOPE")
        self.assertEqual(ctx.exception.code, "PAYOUT_BANK_INVALID")

    def test_unsupported_currency_is_excluded(self):
        self._channel("EURONLY", fee_rate="0.001", balance=5000, currency="EUR")
        usd = self._channel("USDBNK", fee_rate="0.005", balance=5000, currency="USD")
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
            account_number="6200010000000001",
            fee_rate=Decimal("0.001"),
            min_fee=Decimal("1.00"),
            max_fee=Decimal("500.00"),
            currency="USD",
            balance=Decimal("10.00"),
            priority=1,
        )
        BankChannel.objects.create(
            bank_code="MID",
            bank_name="Mid Bank",
            account_number="6200010000000002",
            fee_rate=Decimal("0.002"),
            min_fee=Decimal("1.00"),
            max_fee=Decimal("500.00"),
            currency="USD",
            balance=Decimal("500.00"),
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

    def test_payout_banks_recommends_leftover_split_when_cheapest_is_short(self):
        response = self._call("get", "payout_banks", self.ready.order_no)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["recommended_bank_code"], "CHEAP")
        self.assertEqual(response.data["recommended_bank_codes"], ["CHEAP", "MID"])
        self.assertEqual(
            [(leg["bank_code"], leg["amount"]) for leg in response.data["recommended_split"]],
            [("CHEAP", "10.00"), ("MID", "90.00")],
        )
        codes = [row["bank_code"] for row in response.data["results"]]
        self.assertEqual(codes, ["CHEAP", "MID"])
        cheap = response.data["results"][0]
        self.assertFalse(cheap["sufficient"])
        self.assertTrue(cheap["partial"])
        self.assertTrue(cheap["recommended"])
        self.assertTrue(cheap["selectable"])

    def test_confirm_transfer_auto_selects_leftover_split(self):
        response = self._call("post", "confirm_transfer", self.ready.order_no)
        self.assertEqual(response.status_code, 200, getattr(response, "data", response))
        self.assertEqual(response.data["bank_code"], "CHEAP")
        self.assertEqual(
            [(leg["bank_code"], leg["amount"]) for leg in response.data["payout_splits"]],
            [("CHEAP", "10.00"), ("MID", "90.00")],
        )
        self.ready.refresh_from_db()
        self.assertEqual(self.ready.bank_code, "CHEAP")
        self.assertEqual(self.ready.status, PaymentOrder.OrderStatus.PENDING_SETTLE)
        log = RoutingLog.objects.get(order_no=self.ready.order_no)
        self.assertEqual(log.request_data["splits"][0]["bank_code"], "CHEAP")
        self.assertEqual(log.request_data["splits"][1]["bank_code"], "MID")

    def test_confirm_transfer_explicit_split_uses_remaining_balance(self):
        response = self._call(
            "post",
            "confirm_transfer",
            self.ready.order_no,
            {"bank_codes": ["CHEAP", "MID"]},
        )
        self.assertEqual(response.status_code, 200, getattr(response, "data", response))
        self.assertEqual(
            [(leg["bank_code"], leg["amount"]) for leg in response.data["payout_splits"]],
            [("CHEAP", "10.00"), ("MID", "90.00")],
        )

    def test_confirm_transfer_applies_computed_fee_to_agent_earning(self):
        from apps.agent.models import Agent
        from apps.settlement.models import FeeShare

        agent = Agent.objects.create(
            agent_no="AG-PAYOUT-50",
            agent_name="Payout Agent",
            commission_rate=Decimal("0.500000"),
        )
        self.merchant.agent = agent
        self.merchant.save(update_fields=["agent", "updated_at"])
        self.ready.merchant = self.merchant
        self.ready.save(update_fields=["merchant", "updated_at"])

        response = self._call("post", "confirm_transfer", self.ready.order_no)
        self.assertEqual(response.status_code, 200, getattr(response, "data", response))
        share = FeeShare.objects.get(payment_order=self.ready)
        # CHEAP leftover 10.00 * 0.001 = 0.01; MID remainder 90.00 * 0.002 = 0.18
        # (1.00 remittance fee - 0.19) * 50% = 0.405 → 0.41
        self.assertEqual(share.channel_fee, Decimal("0.19"))
        self.assertEqual(share.agent_fee, Decimal("0.41"))
        self.assertEqual(share.platform_fee, Decimal("0.40"))
        self.assertEqual(share.agent_id, agent.id)


    def test_confirm_transfer_rejects_insufficient_explicit_bank(self):
        response = self._call(
            "post", "confirm_transfer", self.ready.order_no, {"bank_code": "CHEAP"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "PAYOUT_BANK_INSUFFICIENT")
        self.ready.refresh_from_db()
        self.assertEqual(self.ready.status, PaymentOrder.OrderStatus.PENDING_PAY)
        self.assertFalse(self.ready.bank_code)
