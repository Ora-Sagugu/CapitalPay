from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.agent.models import Agent
from apps.exchange.models import ExchangeRate
from apps.merchant.models import Merchant
from apps.payment.models import PaymentOrder
from apps.payment.serializers import build_order_timeline
from apps.payment.services.remittance_application import RemittanceApplicationService
from apps.payment.services.remittance_quote import RemittanceQuoteService
from apps.payment.tests_remittance_v2 import create_eligible_merchant, submit_payload


class OrderStatusCanonicalTests(TestCase):
    def test_legacy_aliases_map_to_live_statuses(self):
        self.assertEqual(PaymentOrder.canonical_status("PRE_CREATE"), "PENDING_PAY")
        self.assertEqual(PaymentOrder.canonical_status("PROCESSING"), "PENDING_PAY")
        self.assertEqual(PaymentOrder.canonical_status("COMPLETED"), "SETTLED")
        self.assertEqual(PaymentOrder.canonical_status("PENDING_PAY"), "PENDING_PAY")
        self.assertEqual(PaymentOrder.canonical_status("SETTLED"), "SETTLED")

    def test_new_order_defaults_to_pending_review(self):
        merchant = Merchant.objects.create(
            merchant_no="STDEF01",
            merchant_name="Status Default",
            status=Merchant.Status.ACTIVE,
        )
        order = PaymentOrder.objects.create(
            order_no="RMT_ST_DEFAULT",
            merchant_order_no="M_ST_DEFAULT",
            unique_identification_no="UIN_ST_DEFAULT",
            idempotency_key="IDEM_ST_DEFAULT",
            merchant=merchant,
            amount=Decimal("10.00"),
            pay_method=PaymentOrder.PayMethod.WIRE_TRANSFER,
            expire_at=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PENDING_REVIEW)


class OrderStatusTimelineTests(TestCase):
    def _order(self, **kwargs):
        merchant = Merchant.objects.create(
            merchant_name="Timeline Merchant",
            status=Merchant.Status.ACTIVE,
        )
        now = timezone.now()
        suffix = timezone.now().strftime("%H%M%S%f")
        values = {
            "order_no": f"RMT_ST_{suffix}",
            "merchant_order_no": f"M_ST_{suffix}",
            "unique_identification_no": f"UIN_ST_{suffix}",
            "idempotency_key": f"IDEM_ST_{suffix}",
            "merchant": merchant,
            "amount": Decimal("100.00"),
            "pay_method": PaymentOrder.PayMethod.WIRE_TRANSFER,
            "expire_at": now + timedelta(days=1),
            "status": PaymentOrder.OrderStatus.SETTLED,
            "reviewed_at": now,
            "pay_received_at": now,
            "settled_at": now,
            "completed_at": None,
        }
        values.update(kwargs)
        return PaymentOrder.objects.create(**values)

    def test_settled_is_the_completed_step(self):
        order = self._order()
        steps = {step["code"]: step for step in build_order_timeline(order)}
        self.assertTrue(steps["completed"]["verified"])
        self.assertFalse(steps["completed"]["active"])
        self.assertTrue(steps["settlement"]["verified"])
        self.assertTrue(bool(steps["completed"]["at"]))

    def test_processing_alias_acts_as_awaiting_funds(self):
        order = self._order(
            status=PaymentOrder.OrderStatus.PROCESSING,
            reviewed_at=timezone.now(),
            pay_received_at=None,
            settled_at=None,
        )
        steps = {step["code"]: step for step in build_order_timeline(order)}
        self.assertTrue(steps["collection"]["active"])
        self.assertFalse(steps["completed"]["verified"])


class RemittanceStatusSequenceTests(TestCase):
    def setUp(self):
        self.merchant = create_eligible_merchant("STSEQ")
        ExchangeRate.objects.create(
            date=timezone.localdate(),
            from_currency="USD",
            to_currency="CNY",
            rate=Decimal("7"),
            source="TEST",
        )

    def _quote(self, actor_type="CUSTOMER", user_id="user-st"):
        return RemittanceQuoteService().create_quote(
            merchant=self.merchant,
            amount=Decimal("1000"),
            from_currency="USD",
            to_currency="CNY",
            fee_bearing="OUR",
            actor_type=actor_type,
            user_id=user_id,
        )

    def test_customer_without_agent_starts_pending_review(self):
        quote = self._quote()
        order, created = RemittanceApplicationService().submit(
            merchant=self.merchant,
            payload=submit_payload(quote),
            idempotency_key="idem-st-seq-1",
            user_id="user-st",
            actor_type="CUSTOMER",
        )
        self.assertTrue(created)
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PENDING_REVIEW)
        self.assertEqual(
            order.agent_review_status, PaymentOrder.AgentReviewStatus.NONE
        )

    def test_agent_submit_skips_agent_review_queue(self):
        quote = self._quote(actor_type="AGENT", user_id="agent-st")
        order, created = RemittanceApplicationService().submit(
            merchant=self.merchant,
            payload=submit_payload(quote),
            idempotency_key="idem-st-seq-2",
            user_id="agent-st",
            actor_type="AGENT",
        )
        self.assertTrue(created)
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PENDING_REVIEW)
        self.assertNotEqual(order.status, PaymentOrder.OrderStatus.PRE_CREATE)
        self.assertNotEqual(order.status, PaymentOrder.OrderStatus.PROCESSING)

    def test_customer_with_agent_starts_pending_agent_review(self):
        agent = Agent.objects.create(
            agent_no="AG_ST_SEQ",
            agent_name="Status Sequence Agent",
            status="ACTIVE",
        )
        self.merchant.agent = agent
        self.merchant.save(update_fields=["agent", "updated_at"])
        quote = self._quote()
        order, created = RemittanceApplicationService().submit(
            merchant=self.merchant,
            payload=submit_payload(quote),
            idempotency_key="idem-st-seq-3",
            user_id="user-st",
            actor_type="CUSTOMER",
        )
        self.assertTrue(created)
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PENDING_AGENT_REVIEW)
        self.assertEqual(
            order.agent_review_status, PaymentOrder.AgentReviewStatus.PENDING
        )

    def test_live_path_excludes_retired_independent_statuses(self):
        live = {
            PaymentOrder.OrderStatus.PENDING_AGENT_REVIEW,
            PaymentOrder.OrderStatus.PENDING_REVIEW,
            PaymentOrder.OrderStatus.PENDING_PAY,
            PaymentOrder.OrderStatus.PAY_RECEIVED,
            PaymentOrder.OrderStatus.PENDING_SETTLE,
            PaymentOrder.OrderStatus.SETTLED,
            PaymentOrder.OrderStatus.CLOSED,
            PaymentOrder.OrderStatus.REFUNDING,
            PaymentOrder.OrderStatus.REFUNDED,
        }
        retired = {
            PaymentOrder.OrderStatus.PRE_CREATE,
            PaymentOrder.OrderStatus.PROCESSING,
            PaymentOrder.OrderStatus.COMPLETED,
        }
        self.assertTrue(live.isdisjoint(retired))
        for code in retired:
            self.assertIn(code, PaymentOrder.LEGACY_STATUS_ALIASES)
            self.assertIn(PaymentOrder.canonical_status(code), live)
