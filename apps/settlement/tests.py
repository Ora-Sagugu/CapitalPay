"""清算资金划拨测试。"""
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.merchant.models import Merchant
from apps.payment.gateway import BankGatewayRouter
from apps.settlement.engine.distributor import FundsDistributor
from apps.settlement.models import SettlementBatch


@override_settings(BANK_GATEWAY_MODE="MOCK", BANK_CODES=["MOCK"])
class FundsDistributorTest(TestCase):
    def setUp(self):
        BankGatewayRouter._bootstrapped = False
        BankGatewayRouter._gateways = {}
        self.merchant = Merchant.objects.create(
            merchant_no="SET_M001",
            merchant_name="清算测试商户",
            status=Merchant.Status.ACTIVE,
            api_key="ak_set_001",
            api_secret="sk_set_secret",
        )
        self.batch = SettlementBatch.objects.create(
            batch_no="SB20260101001",
            settle_date=timezone.now().date(),
            merchant=self.merchant,
            total_count=1,
            total_amount=Decimal("1000.00"),
            fee_total=Decimal("10.00"),
            settle_net_amount=Decimal("990.00"),
            status=SettlementBatch.SettleStatus.PENDING,
            settlement_account_info={"bank_code": "MOCK", "from_account": "N1", "to_account": "M1"},
        )

    def test_distribute_success(self):
        result = FundsDistributor().distribute(self.batch)
        self.assertEqual(result.status, SettlementBatch.SettleStatus.SETTLED)
        self.assertIsNotNone(result.settled_at)
