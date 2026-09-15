"""功能清单缺口回归：预下单状态、手续费回落、关单、调账过账。"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.merchant.models import Merchant, MerchantFee, MerchantSplitConfig
from apps.merchant.services import MerchantService
from apps.param.models import CoopBank, FeeModel, BankFeeConfig
from apps.param.services import resolve_channel_rate, compute_fee_from_model
from apps.payment.models import PaymentOrder
from apps.payment.services.pre_order import PreOrderService, build_cashier_url
from apps.payment.services.close_order import CloseOrderService
from apps.payment.services.payment import PaymentConfirmService
from apps.adjustment.models import AdjustmentApplication
from apps.adjustment.services import AdjustmentService
from apps.account.models import NostroAccount


class PreOrderGapTest(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(
            merchant_no="GAP_M001", merchant_name="缺口测试商户",
            api_key="ak_gap_001", api_secret="sk_gap",
            status=Merchant.Status.ACTIVE,
        )
        MerchantService().set_fee(self.merchant, {
            "product_type": MerchantFee.ProductType.WIRE_TRANSFER,
            "fee_model": MerchantFee.FeeModel.PERCENTAGE,
            "fee_rate": Decimal("0.003"),
            "min_fee": Decimal("1.00"),
            "effective_from": timezone.now().date(),
        })

    def test_pre_order_pending_pay_and_cashier_url(self):
        order = PreOrderService().create_pre_order(
            merchant_no="GAP_M001",
            merchant_order_no="MO_GAP_1",
            amount=Decimal("1000.00"),
            pay_method="WIRE_TRANSFER",
            notify_url="https://example.com/cb",
        )
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PENDING_PAY)
        url = build_cashier_url(order)
        self.assertIn(order.order_no, url)
        self.assertIn(order.unique_identification_no, url)

    def test_close_pending_pay(self):
        order = PreOrderService().create_pre_order(
            merchant_no="GAP_M001", merchant_order_no="MO_GAP_2",
            amount=Decimal("1000.00"), pay_method="WIRE_TRANSFER",
        )
        CloseOrderService().close_order(order)
        order.refresh_from_db()
        self.assertEqual(order.status, PaymentOrder.OrderStatus.CLOSED)

    def test_uin_match_pending_pay(self):
        order = PreOrderService().create_pre_order(
            merchant_no="GAP_M001", merchant_order_no="MO_GAP_3",
            amount=Decimal("2000.00"), pay_method="WIRE_TRANSFER",
        )
        matched = PaymentConfirmService().auto_match_wire_transfer({
            "txn_id": "TXN_GAP",
            "amount": Decimal("2000.00"),
            "remark": order.unique_identification_no,
            "txn_time": timezone.now(),
            "bank_code": "MOCK",
        })
        self.assertIsNotNone(matched)
        self.assertEqual(matched.status, PaymentOrder.OrderStatus.PAY_RECEIVED)


class FeeFallbackTest(TestCase):
    def test_fee_model_fallback(self):
        merchant = Merchant.objects.create(
            merchant_no="GAP_M002", merchant_name="无产品费率商户",
            api_key="ak_gap_002", api_secret="sk",
        )
        FeeModel.objects.create(
            model_code="FB1", model_name="回落", fee_type="fixed",
            base_rate=Decimal("0.01"), min_fee=Decimal("1"), max_fee=Decimal("100"),
        )
        result = MerchantService().calculate_fee(merchant, Decimal("1000"), "ONLINE_BANK")
        self.assertEqual(result["fee_amount"], Decimal("10.00"))

    def test_channel_rate_from_bank_fee_config(self):
        bank = CoopBank.objects.create(bank_code="GAPB", bank_name="Gap Bank")
        model = FeeModel.objects.create(
            model_code="CH1", model_name="渠道", base_rate=Decimal("0.005"),
        )
        BankFeeConfig.objects.create(
            bank=bank, fee_model=model, channel_type="wire",
            override_rate=Decimal("0.002"),
        )
        self.assertEqual(resolve_channel_rate("GAPB", "WIRE_TRANSFER"), Decimal("0.002"))

    def test_compute_mixed_fee(self):
        model = FeeModel.objects.create(
            model_code="MX1", model_name="混合", fee_type="mixed",
            base_rate=Decimal("0.001"), min_fee=Decimal("5"), max_fee=Decimal("50"),
        )
        fee = compute_fee_from_model(model, Decimal("1000"))
        self.assertEqual(fee, Decimal("6.00"))


class SplitAndAdjustmentTest(TestCase):
    def test_split_config_defaults(self):
        merchant = Merchant.objects.create(
            merchant_no="GAP_M003", merchant_name="分账商户",
            api_key="ak_gap_003", api_secret="sk",
        )
        cfg = MerchantSplitConfig.objects.create(merchant=merchant)
        self.assertTrue(cfg.auto_split)
        self.assertEqual(cfg.merchant_ratio, Decimal("1.0000"))

    def test_adjustment_posts_nostro(self):
        merchant = Merchant.objects.create(
            merchant_no="GAP_M004", merchant_name="调账商户",
            api_key="ak_gap_004", api_secret="sk",
        )
        acc = NostroAccount.objects.create(
            account_no="NOS_GAP_1", bank_code="MOCK", bank_name="Mock",
            account_number="123", merchant=merchant, balance=Decimal("100.00"),
        )
        app = AdjustmentService.create_application({
            "diff_type": "amount",
            "order_no": "",
            "bank_channel": "Mock",
            "amount": Decimal("10"),
            "adjustment_amount": Decimal("10"),
            "reason": "test",
            "applicant": "tester",
        })
        AdjustmentService.approve_application(str(app.id), "approver", "1", "ok")
        acc.refresh_from_db()
        self.assertEqual(acc.balance, Decimal("110.00"))
        app.refresh_from_db()
        self.assertEqual(app.status, AdjustmentApplication.Status.COMPLETED)


class PayNotifyRoutingTest(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(
            merchant_no="GAP_M010", merchant_name="支付通知商户",
            api_key="ak_gap_010", api_secret="sk_gap",
            status=Merchant.Status.ACTIVE,
        )
        MerchantService().set_fee(self.merchant, {
            "product_type": MerchantFee.ProductType.WIRE_TRANSFER,
            "fee_model": MerchantFee.FeeModel.PERCENTAGE,
            "fee_rate": Decimal("0.003"),
            "min_fee": Decimal("1.00"),
            "effective_from": timezone.now().date(),
        })
        MerchantService().set_fee(self.merchant, {
            "product_type": MerchantFee.ProductType.ONLINE_BANK,
            "fee_model": MerchantFee.FeeModel.PERCENTAGE,
            "fee_rate": Decimal("0.003"),
            "min_fee": Decimal("1.00"),
            "effective_from": timezone.now().date(),
        })
        MerchantService().set_fee(self.merchant, {
            "product_type": MerchantFee.ProductType.AUTHORIZED,
            "fee_model": MerchantFee.FeeModel.FIXED,
            "fixed_fee": Decimal("2.00"),
            "effective_from": timezone.now().date(),
        })

    def test_notify_on_confirm(self):
        from unittest.mock import patch
        order = PreOrderService().create_pre_order(
            merchant_no="GAP_M010", merchant_order_no="MO_NTF",
            amount=Decimal("100.00"), pay_method="WIRE_TRANSFER",
            notify_url="https://example.com/cb",
        )
        with patch("apps.payment.tasks.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            PaymentConfirmService().auto_match_wire_transfer({
                "txn_id": "TXN_NTF",
                "amount": Decimal("100.00"),
                "remark": order.unique_identification_no,
                "txn_time": timezone.now(),
                "bank_code": "MOCK",
            })
            self.assertTrue(mock_post.called)
        order.refresh_from_db()
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PAY_RECEIVED)
        self.assertEqual(order.notify_status, "SUCCESS")

    def test_cashier_online_bank_pay(self):
        from django.test import Client
        order = PreOrderService().create_pre_order(
            merchant_no="GAP_M010", merchant_order_no="MO_CASH",
            amount=Decimal("200.00"), pay_method="ONLINE_BANK",
        )
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PENDING_PAY)
        client = Client()
        resp = client.get(f"/api/v1/cashier/orders/{order.order_no}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["order_no"], order.order_no)
        resp = client.post(
            f"/api/v1/cashier/orders/{order.order_no}/pay/",
            {"uin": order.unique_identification_no},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PAY_RECEIVED)

    def test_authorized_auto_confirm(self):
        from apps.account.services import AccountService
        AccountService().bind_account(
            user_id="U_GAP",
            merchant_id=self.merchant,
            bank_code="MOCK",
            bank_name="Mock",
            account_holder="Tester",
            account_number="62220001",
            bind_token="",
        )
        order = PreOrderService().create_pre_order(
            merchant_no="GAP_M010", merchant_order_no="MO_AUTH",
            amount=Decimal("50.00"), pay_method="AUTHORIZED", user_id="U_GAP",
        )
        order.refresh_from_db()
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PAY_RECEIVED)

    def test_routing_log_on_pre_order(self):
        from apps.routing.models import BankChannel, RoutingLog
        BankChannel.objects.create(bank_code="MOCK", bank_name="Mock Bank")
        order = PreOrderService().create_pre_order(
            merchant_no="GAP_M010", merchant_order_no="MO_RTE",
            amount=Decimal("80.00"), pay_method="WIRE_TRANSFER",
        )
        self.assertTrue(RoutingLog.objects.filter(order_no=order.order_no).exists())


class ReportWriteOffReconTest(TestCase):
    def test_generate_daily_reports(self):
        from datetime import date
        from apps.report.services import ReportGenerator
        Merchant.objects.create(
            merchant_no="GAP_M011", merchant_name="报表商户",
            api_key="ak_gap_011", api_secret="sk",
            status=Merchant.Status.ACTIVE,
        )
        result = ReportGenerator().generate_all(date.today())
        self.assertGreaterEqual(result["merchant_daily"], 1)
        self.assertGreaterEqual(result["platform_summary"], 1)

    def test_write_off_posts_nostro(self):
        from apps.settlement.models import DifferenceWriteOff
        from apps.account.services import AccountService
        merchant = Merchant.objects.create(
            merchant_no="GAP_M012", merchant_name="代销账商户",
            api_key="ak_gap_012", api_secret="sk",
        )
        acc = NostroAccount.objects.create(
            account_no="NOS_WOF_1", bank_code="MOCK", bank_name="Mock",
            account_number="999", merchant=merchant, balance=Decimal("20.00"),
        )
        wo = DifferenceWriteOff.objects.create(
            write_off_no="WOF_GAP_1", merchant=merchant, amount=Decimal("5.00"),
            reason="test", applied_by="t",
            status=DifferenceWriteOff.WriteOffStatus.APPROVED,
        )
        AccountService().update_balance(acc, wo.amount, is_credit=True)
        wo.status = DifferenceWriteOff.WriteOffStatus.WRITTEN_OFF
        wo.save(update_fields=["status"])
        acc.refresh_from_db()
        self.assertEqual(acc.balance, Decimal("25.00"))
        wo.refresh_from_db()
        self.assertEqual(wo.status, DifferenceWriteOff.WriteOffStatus.WRITTEN_OFF)

    def test_settlement_fund_reconciliation(self):
        from apps.reconciliation.tasks import run_settlement_fund_reconciliation
        from apps.reconciliation.models import ReconciliationBatch
        recon = run_settlement_fund_reconciliation()
        self.assertEqual(recon.recon_type, "SETTLEMENT_FUND")
        self.assertTrue(
            ReconciliationBatch.objects.filter(id=recon.id, recon_type="SETTLEMENT_FUND").exists()
        )

    def test_execute_transfer_uses_gateway(self):
        from apps.account.services import AccountService
        from apps.account.models import FundTransfer
        merchant = Merchant.objects.create(
            merchant_no="GAP_M013", merchant_name="调拨商户",
            api_key="ak_gap_013", api_secret="sk",
        )
        a = NostroAccount.objects.create(
            account_no="NOS_T_A", bank_code="MOCK", bank_name="Mock",
            account_number="A1", merchant=merchant, balance=Decimal("50.00"),
        )
        b = NostroAccount.objects.create(
            account_no="NOS_T_B", bank_code="MOCK", bank_name="Mock",
            account_number="B1", merchant=merchant, balance=Decimal("0.00"),
        )
        transfer = AccountService().create_transfer(
            from_account=a, to_account=b, amount=Decimal("10.00"), remark="gap",
        )
        AccountService().execute_transfer(transfer)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, FundTransfer.TransferStatus.SUCCESS)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.balance, Decimal("40.00"))
        self.assertEqual(b.balance, Decimal("10.00"))
