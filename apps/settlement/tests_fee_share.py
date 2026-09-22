from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.agent.models import Agent
from apps.core.exceptions import BusinessException
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
        self.assertEqual(share.platform_fee, Decimal("5.26"))

    def test_serializer_emits_two_decimal_strings(self):
        share = SettlementCalculator().calculate_fee_share(
            self.order, channel_rate=Decimal("0.0033")
        )
        data = FeeShareSerializer(share).data
        self.assertEqual(data["amount"], "123.45")
        self.assertEqual(data["total_fee"], "5.67")
        self.assertEqual(data["channel_fee"], "0.41")
        self.assertEqual(data["platform_fee"], "5.26")
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
        self.assertEqual(share.agent_fee, Decimal("2.63"))
        self.assertEqual(share.platform_fee, Decimal("2.63"))
        self.assertEqual(share.agent_id, self.agent.id)

    def test_full_share_gives_agent_the_net_profit(self):
        self.agent.commission_rate = Decimal("1.000000")
        self.agent.save(update_fields=["commission_rate"])
        share = SettlementCalculator().calculate_fee_share(
            self.order, channel_rate=Decimal("0.0033")
        )
        self.assertEqual(share.channel_fee, Decimal("0.41"))
        self.assertEqual(share.agent_fee, Decimal("5.26"))
        self.assertEqual(share.platform_fee, Decimal("0.00"))
        self.assertEqual(share.agent_id, self.agent.id)

    def test_independent_merchant_keeps_net_profit_on_the_platform(self):
        independent = Merchant.objects.create(
            merchant_no="FSIND01",
            merchant_name="Independent Customer",
            status=Merchant.Status.ACTIVE,
        )
        order = PaymentOrder.objects.create(
            order_no="RMT_FS_IND_001",
            merchant_order_no="M_FS_IND",
            unique_identification_no="UIN_FS_IND",
            idempotency_key="IDEM_FS_IND",
            merchant=independent,
            amount=Decimal("123.45"),
            currency="USD",
            fee_amount=Decimal("5.67"),
            settle_amount=Decimal("117.78"),
            status="PENDING_PAY",
            expire_at=timezone.now(),
        )
        share = SettlementCalculator().calculate_fee_share(
            order, channel_rate=Decimal("0.0033")
        )
        self.assertEqual(share.channel_fee, Decimal("0.41"))
        self.assertEqual(share.agent_fee, Decimal("0.00"))
        self.assertEqual(share.platform_fee, Decimal("5.26"))
        self.assertIsNone(share.agent_id)


class ChannelMaxFeeShareTests(TestCase):
    def setUp(self):
        from apps.routing.models import BankChannel

        self.merchant = Merchant.objects.create(
            merchant_no="FSMAX01",
            merchant_name="Max Fee Co",
            status=Merchant.Status.ACTIVE,
        )
        self.channel = BankChannel.objects.create(
            bank_code="MAXCAP",
            bank_name="Max Cap Bank",
            account_number="6222029999000001",
            fee_rate=Decimal("0.0008"),
            max_fee=Decimal("20.00"),
        )
        self.order = PaymentOrder.objects.create(
            order_no="RMT_FS_MAX_001",
            merchant_order_no="M_FS_MAX",
            unique_identification_no="UIN_FS_MAX",
            idempotency_key="IDEM_FS_MAX",
            merchant=self.merchant,
            amount=Decimal("100000.00"),
            currency="USD",
            fee_amount=Decimal("50.00"),
            settle_amount=Decimal("99950.00"),
            status="PENDING_PAY",
            bank_code=self.channel.bank_code,
            expire_at=timezone.now(),
        )

    def test_settlement_channel_fee_respects_max_fee(self):
        share = SettlementCalculator().calculate_fee_share(self.order)
        # 100000 * 0.0008 = 80, capped at 20
        self.assertEqual(share.channel_fee, Decimal("20.00"))
        self.assertEqual(share.bank_channel_name, "Max Cap Bank")
        self.assertEqual(share.platform_fee, Decimal("30.00"))
        self.assertEqual(share.agent_fee, Decimal("0.00"))


class AgentEarningFromComputedFeeTests(TestCase):
    def setUp(self):
        from apps.routing.models import BankChannel

        self.agent = Agent.objects.create(
            agent_no="AG-NET-50",
            agent_name="Net Agent",
            commission_rate=Decimal("0.500000"),
        )
        self.merchant = Merchant.objects.create(
            merchant_no="FSNET01",
            merchant_name="Net Customer",
            status=Merchant.Status.ACTIVE,
            agent=self.agent,
        )
        self.channel = BankChannel.objects.create(
            bank_code="NETCAP",
            bank_name="Net Cap Bank",
            account_number="6222029999000002",
            fee_rate=Decimal("0.0008"),
            max_fee=Decimal("20.00"),
        )
        self.order = PaymentOrder.objects.create(
            order_no="RMT_FS_NET_001",
            merchant_order_no="M_FS_NET",
            unique_identification_no="UIN_FS_NET",
            idempotency_key="IDEM_FS_NET",
            merchant=self.merchant,
            amount=Decimal("100000.00"),
            sender_total_amount=Decimal("100000.00"),
            currency="USD",
            fee_amount=Decimal("50.00"),
            settle_amount=Decimal("99950.00"),
            status="PENDING_PAY",
            bank_code=self.channel.bank_code,
            expire_at=timezone.now(),
        )

    def test_agent_earning_is_share_of_remittance_fee_minus_computed_fee(self):
        share = SettlementCalculator().calculate_fee_share(self.order)
        # Computed fee 100000 * 0.0008 = 80, capped at 20
        # Net 50.00 - 20.00 = 30.00; 50% share = 15.00
        self.assertEqual(share.channel_fee, Decimal("20.00"))
        self.assertEqual(share.agent_fee, Decimal("15.00"))
        self.assertEqual(share.platform_fee, Decimal("15.00"))
        self.assertEqual(share.agent_id, self.agent.id)

    def test_bank_fee_must_be_less_than_remittance_fee(self):
        self.order.fee_amount = Decimal("5.00")
        self.order.save(update_fields=["fee_amount"])
        with self.assertRaises(BusinessException) as ctx:
            SettlementCalculator().calculate_fee_share(self.order)
        self.assertEqual(ctx.exception.code, "PAYOUT_BANK_FEE_EXCEEDS")


class SplitPayoutFeeShareTests(TestCase):
    def test_channel_fee_sums_each_bank_leg(self):
        from apps.routing.models import BankChannel

        merchant = Merchant.objects.create(
            merchant_no="FSSPL01",
            merchant_name="Split Fee Co",
            status=Merchant.Status.ACTIVE,
        )
        BankChannel.objects.create(
            bank_code="CHEAP",
            bank_name="Cheap Bank",
            account_number="6222028888000001",
            fee_rate=Decimal("0.001"),
            max_fee=Decimal("500.00"),
        )
        BankChannel.objects.create(
            bank_code="MID",
            bank_name="Mid Bank",
            account_number="6222028888000002",
            fee_rate=Decimal("0.002"),
            max_fee=Decimal("500.00"),
        )
        order = PaymentOrder.objects.create(
            order_no="RMT_FS_SPLIT_001",
            merchant_order_no="M_FS_SPLIT",
            unique_identification_no="UIN_FS_SPLIT",
            idempotency_key="IDEM_FS_SPLIT",
            merchant=merchant,
            amount=Decimal("100.00"),
            sender_total_amount=Decimal("100.00"),
            currency="USD",
            fee_amount=Decimal("1.00"),
            settle_amount=Decimal("99.00"),
            status="PENDING_PAY",
            bank_code="CHEAP",
            payout_splits=[
                {"bank_code": "CHEAP", "bank_name": "Cheap Bank", "amount": "20.00"},
                {"bank_code": "MID", "bank_name": "Mid Bank", "amount": "80.00"},
            ],
            expire_at=timezone.now(),
        )
        share = SettlementCalculator().calculate_fee_share(order)
        self.assertEqual(share.channel_fee, Decimal("0.18"))
        self.assertEqual(share.bank_channel_name, "Cheap Bank + Mid Bank")
        self.assertEqual(share.platform_fee, Decimal("0.82"))
