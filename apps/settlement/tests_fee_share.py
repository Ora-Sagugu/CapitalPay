from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.agent.models import Agent
from apps.merchant.models import Merchant
from apps.payment.models import PaymentOrder
from apps.settlement.engine.calculator import SettlementCalculator
from apps.settlement.serializers import FeeShareSerializer
from apps.settlement.views import _money_str


class FeeShareTwoDecimalTests(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(
            merchant_no="FS2DP01",
            merchant_name="Fee Share Co",
            status=Merchant.Status.ACTIVE,
        )
        self.order = PaymentOrder.objects.create(
            order_no="RMT_FS_2DP_001",
            merchant_order_no="M_FS_001",
            unique_identification_no="UIN_FS_001",
            idempotency_key="IDEM_FS_001",
            merchant=self.merchant,
            amount=Decimal("123.45"),
            currency="USD",
            fee_amount=Decimal("5.67"),
            settle_amount=Decimal("117.78"),
            status="PENDING_PAY",
            expire_at=timezone.now(),
        )

    def test_calculator_quantizes_fees_to_two_decimals(self):
        share = SettlementCalculator().calculate_fee_share(
            self.order, channel_rate=Decimal("0.0033")
        )
        self.assertEqual(share.amount, Decimal("123.45"))
        self.assertEqual(share.total_fee, Decimal("5.67"))
        self.assertEqual(share.channel_fee, Decimal("0.41"))  # 123.45 * 0.0033 = 0.407385
        self.assertEqual(share.agent_fee, Decimal("0.00"))
        self.assertEqual(share.platform_fee, Decimal("5.67"))

    def test_serializer_emits_two_decimal_strings(self):
        share = SettlementCalculator().calculate_fee_share(
            self.order, channel_rate=Decimal("0.0033")
        )
        data = FeeShareSerializer(share).data
        self.assertEqual(data["amount"], "123.45")
        self.assertEqual(data["total_fee"], "5.67")
        self.assertEqual(data["channel_fee"], "0.41")
        self.assertEqual(data["platform_fee"], "5.67")
        self.assertEqual(data["agent_fee"], "0.00")

    def test_stats_helper_formats_two_decimals(self):
        self.assertEqual(_money_str(None), "0.00")
        self.assertEqual(_money_str(Decimal("12.3400")), "12.34")
        self.assertEqual(_money_str("1"), "1.00")


class AgentFeeShareSplitTests(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(
            agent_no="AG-SHARE-50",
            agent_name="Share Agent",
            commission_rate=Decimal("0.500000"),
        )
        self.merchant = Merchant.objects.create(
            merchant_no="FS50AG01",
            merchant_name="Share Customer",
            status=Merchant.Status.ACTIVE,
            agent=self.agent,
        )
        self.order = PaymentOrder.objects.create(
            order_no="RMT_FS_SHARE_001",
            merchant_order_no="M_FS_SHARE",
            unique_identification_no="UIN_FS_SHARE",
            idempotency_key="IDEM_FS_SHARE",
            merchant=self.merchant,
            amount=Decimal("123.45"),
            currency="USD",
            fee_amount=Decimal("5.67"),
            settle_amount=Decimal("117.78"),
            status="PENDING_PAY",
            expire_at=timezone.now(),
        )

    def test_fifty_percent_of_customer_fee(self):
        share = SettlementCalculator().calculate_fee_share(
            self.order, channel_rate=Decimal("0.0033")
        )
        self.assertEqual(share.channel_fee, Decimal("0.41"))
        self.assertEqual(share.agent_fee, Decimal("2.84"))
        self.assertEqual(share.platform_fee, Decimal("2.83"))

    def test_full_share_gives_entire_customer_fee_to_agent(self):
        self.agent.commission_rate = Decimal("1.000000")
        self.agent.save(update_fields=["commission_rate"])
        share = SettlementCalculator().calculate_fee_share(
            self.order, channel_rate=Decimal("0.0033")
        )
        self.assertEqual(share.channel_fee, Decimal("0.41"))
        self.assertEqual(share.agent_fee, Decimal("5.67"))
        self.assertEqual(share.platform_fee, Decimal("0.00"))
