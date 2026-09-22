from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.agent.models import Agent
from apps.merchant.models import Merchant
from apps.payment.models import PaymentOrder
from apps.payment.serializers import PaymentOrderDetailSerializer, resolve_order_fee_breakdown
from apps.routing.models import BankChannel
from apps.settlement.engine.calculator import SettlementCalculator
from apps.user_portal.services import UserService


class OrderDetailFeeBreakdownTests(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(
            agent_no="AG-ODF-50",
            agent_name="Order Detail Agent",
            commission_rate=Decimal("0.500000"),
        )
        self.merchant = Merchant.objects.create(
            merchant_no="ODF001",
            merchant_name="Order Detail Fee Co",
            status=Merchant.Status.ACTIVE,
            agent=self.agent,
        )
        self.channel = BankChannel.objects.create(
            bank_code="CHEAP",
            bank_name="Cheap Bank",
            account_number="100200300400",
            fee_rate=Decimal("0.003300"),
            max_fee=Decimal("20.00"),
            status=BankChannel.Status.ACTIVE,
        )
        self.order = PaymentOrder.objects.create(
            order_no="RMT_ODF_001",
            merchant_order_no="M_ODF_001",
            unique_identification_no="UIN_ODF_001",
            idempotency_key="IDEM_ODF_001",
            merchant=self.merchant,
            amount=Decimal("123.45"),
            currency="USD",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("5.67"),
            fee_currency="USD",
            settle_amount=Decimal("117.78"),
            status="PENDING_PAY",
            expire_at=timezone.now(),
        )

    def test_breakdown_null_before_payout_bank_selected(self):
        data = resolve_order_fee_breakdown(self.order)
        self.assertIsNone(data["bank_fee"])
        self.assertIsNone(data["remittance_profit"])
        self.assertIsNone(data["agent_fee"])
        self.assertIsNone(data["capitalpay_profit"])

        payload = PaymentOrderDetailSerializer(self.order).data
        self.assertIsNone(payload["bank_fee"])
        self.assertIsNone(payload["remittance_profit"])
        self.assertIsNone(payload["agent_fee"])
        self.assertIsNone(payload["capitalpay_profit"])

    def test_breakdown_splits_remittance_profit_by_agent_share(self):
        self.order.bank_code = self.channel.bank_code
        self.order.save(update_fields=["bank_code", "updated_at"])
        SettlementCalculator().calculate_fee_share(self.order)

        data = resolve_order_fee_breakdown(self.order)
        self.assertEqual(data["bank_fee"], Decimal("0.41"))
        self.assertEqual(data["remittance_profit"], Decimal("5.26"))
        self.assertEqual(data["agent_fee"], Decimal("2.63"))
        self.assertEqual(data["capitalpay_profit"], Decimal("2.63"))

        payload = PaymentOrderDetailSerializer(self.order).data
        self.assertEqual(payload["bank_fee"], "0.41")
        self.assertEqual(payload["remittance_profit"], "5.26")
        self.assertEqual(payload["agent_fee"], "2.63")
        self.assertEqual(payload["capitalpay_profit"], "2.63")

    def test_agent_orders_agent_fee_matches_ops_order_detail(self):
        self.order.bank_code = self.channel.bank_code
        self.order.save(update_fields=["bank_code", "updated_at"])
        SettlementCalculator().calculate_fee_share(self.order)

        ops_fee = PaymentOrderDetailSerializer(self.order).data["agent_fee"]
        agent_fee = UserService._order_agent_fee(self.order)
        self.assertEqual(agent_fee, ops_fee)
        self.assertEqual(agent_fee, "2.63")

    def test_independent_merchant_keeps_all_profit_as_capitalpay(self):
        independent = Merchant.objects.create(
            merchant_no="ODFIND01",
            merchant_name="Independent Co",
            status=Merchant.Status.ACTIVE,
        )
        order = PaymentOrder.objects.create(
            order_no="RMT_ODF_IND",
            merchant_order_no="M_ODF_IND",
            unique_identification_no="UIN_ODF_IND",
            idempotency_key="IDEM_ODF_IND",
            merchant=independent,
            amount=Decimal("123.45"),
            currency="USD",
            fee_amount=Decimal("5.67"),
            settle_amount=Decimal("117.78"),
            status="PENDING_PAY",
            bank_code=self.channel.bank_code,
            expire_at=timezone.now(),
        )
        SettlementCalculator().calculate_fee_share(order)

        data = resolve_order_fee_breakdown(order)
        self.assertEqual(data["remittance_profit"], Decimal("5.26"))
        self.assertEqual(data["agent_fee"], Decimal("0.00"))
        self.assertEqual(data["capitalpay_profit"], Decimal("5.26"))

    @override_settings(ENABLE_BANKING=False)
    def test_breakdown_when_banking_disabled(self):
        data = resolve_order_fee_breakdown(self.order)
        self.assertEqual(data["bank_fee"], Decimal("0.00"))
        self.assertEqual(data["remittance_profit"], Decimal("5.67"))
        self.assertIsNone(data["agent_fee"])
        self.assertIsNone(data["capitalpay_profit"])
