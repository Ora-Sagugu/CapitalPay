"""银行网关 Mock / Router 单元测试。"""
from decimal import Decimal

from django.test import TestCase, override_settings

from apps.payment.gateway import BankGatewayRouter, MockBankGateway, RealBankGateway


class MockBankGatewayTest(TestCase):
    def setUp(self):
        self.gw = MockBankGateway()

    def test_transfer_success(self):
        result = self.gw.transfer(
            from_account="A",
            to_account="B",
            amount=Decimal("100.00"),
            currency="CNY",
            transfer_no="T001",
        )
        self.assertTrue(result["success"])
        self.assertIn("MOCK_TRF_", result["bank_txn_id"])

    def test_disburse_success(self):
        result = self.gw.disburse(
            payee_bank_name="Bank",
            payee_account_no="6222",
            payee_account_holder="Zhang",
            amount=Decimal("50.00"),
            currency="USD",
            disbursement_no="D001",
        )
        self.assertTrue(result["success"])

    def test_request_adjustment_success(self):
        result = self.gw.request_adjustment(
            bank_txn_id="TXN1",
            amount=Decimal("10"),
            reason="diff",
            diff_id="1",
        )
        self.assertTrue(result["success"])


@override_settings(BANK_GATEWAY_MODE="MOCK", BANK_CODES=["MOCK"])
class BankGatewayRouterTest(TestCase):
    def setUp(self):
        BankGatewayRouter._bootstrapped = False
        BankGatewayRouter._gateways = {}

    def test_get_gateway_mock(self):
        gw = BankGatewayRouter.get_gateway("MOCK")
        self.assertIsInstance(gw, MockBankGateway)

    def test_list_banks(self):
        banks = BankGatewayRouter.list_banks()
        self.assertTrue(any(b["bank_code"] == "MOCK" for b in banks))


@override_settings(BANK_GATEWAY_MODE="REAL", BANK_CODES=["ABC"], BANK_API_KEYS={})
class RealBankGatewayTest(TestCase):
    def setUp(self):
        BankGatewayRouter._bootstrapped = False
        BankGatewayRouter._gateways = {}

    def test_real_raises_without_credentials(self):
        gw = RealBankGateway("ABC")
        with self.assertRaises(NotImplementedError):
            gw.transfer(
                from_account="A",
                to_account="B",
                amount=Decimal("1"),
                currency="CNY",
                transfer_no="T",
            )
