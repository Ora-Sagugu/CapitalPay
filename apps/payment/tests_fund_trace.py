"""款项追踪 — OR 检索、多笔命中、VA 解析、next_hop。"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.account.models import NostroAccount, VirtualAccount
from apps.merchant.models import Merchant
from apps.payment.models import PaymentOrder
from apps.payment.services.fund_trace import FundTraceNotFound, trace_fund
from apps.payment.views import PaymentOrderViewSet
from apps.rbac.models import Role, SystemUser, UserRole


class FundTraceServiceTests(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(
            merchant_name="Peter",
            status=Merchant.Status.ACTIVE,
        )
        self.expire = timezone.now() + timedelta(days=7)
        self.orders = [
            self._order(
                "RMT_TRACE_001", "M_TRACE_001", "ABC Company", "111111",
                status="COMPLETED", amount="1000.00", fee="1.00", settle="999.00",
            ),
            self._order(
                "RMT_TRACE_002", "M_TRACE_002", "XIAOMI", "Citi Bank",
                status="PENDING_PAY", amount="2000.00", fee="2.00", settle="1998.00",
            ),
            self._order(
                "RMT_TRACE_003", "M_TRACE_003", "ABCC", "100000",
                status="PENDING_REVIEW", amount="500.00", fee="1.00", settle="499.00",
            ),
        ]
        self.master = NostroAccount.objects.create(
            merchant=self.merchant,
            account_no="N_TRACE_001",
            bank_code="NSTR",
            bank_name="CapitalPay Nostro",
            account_number="ACCT-PETER",
            account_type=NostroAccount.AccountType.COLLECTION,
            currency="CNY",
            balance=Decimal("8888.00"),
        )
        self.va = VirtualAccount.objects.create(
            master_account=self.master,
            merchant=self.merchant,
            va_number="VAV20260827TRACE01",
            va_type=VirtualAccount.VaType.VAV,
            label="Peter Collection VA",
            bank_code="NSTR",
            bank_name="CapitalPay Nostro",
            account_holder="Peter",
            currency="CNY",
            ledger_balance=Decimal("1200.00"),
            available_balance=Decimal("1200.00"),
            status=VirtualAccount.VaStatus.ACTIVE,
        )

    def _order(self, order_no, merchant_order_no, beneficiary, bank, status, amount, fee, settle):
        return PaymentOrder.objects.create(
            order_no=order_no,
            merchant_order_no=merchant_order_no,
            unique_identification_no=f"UIN_{order_no}",
            idempotency_key=f"IDEM_{order_no}",
            merchant=self.merchant,
            amount=Decimal(amount),
            currency="CNY",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal(fee),
            settle_amount=Decimal(settle),
            status=status,
            pay_method="WIRE_TRANSFER",
            beneficiary_name=beneficiary,
            beneficiary_bank=bank,
            expire_at=self.expire,
        )

    def test_q_peter_returns_matches_and_default_order(self):
        data = trace_fund(q="peter")
        self.assertEqual(data["match_count"], 3)
        self.assertEqual(len(data["matches"]), 3)
        self.assertEqual(data["order"]["remitter_name"], "Peter")
        self.assertIn(data["order"]["order_no"], {o.order_no for o in self.orders})

    def test_legacy_same_keyword_is_or_not_and(self):
        data = trace_fund(
            order_no="peter",
            merchant_order_no="peter",
            prn="peter",
            remitter_name="peter",
        )
        self.assertEqual(data["match_count"], 3)

    def test_order_includes_fee_settle_and_next_hop(self):
        data = trace_fund(q="RMT_TRACE_001")
        order = data["order"]
        self.assertEqual(order["fee_amount"], "1.00")
        self.assertEqual(order["settle_amount"], "999.00")
        self.assertEqual(order["next_hop"]["code"], "delivered_beneficiary")
        self.assertEqual(order["next_hop"]["target"], "beneficiary")

    def test_completed_next_hop_code(self):
        data = trace_fund(q="RMT_TRACE_001")
        self.assertEqual(data["order"]["next_hop"]["code"], "delivered_beneficiary")

    def test_merchant_vav_resolved_without_order_fk(self):
        data = trace_fund(q="RMT_TRACE_001")
        va = data["order"]["virtual_account"]
        self.assertIsNotNone(va)
        self.assertEqual(va["va_number"], "VAV20260827TRACE01")
        self.assertEqual(va["va_type"], "VAV")
        self.assertEqual(va["master_account_no"], "N_TRACE_001")
        self.assertEqual(va["master_balance"], "8888.00")
        self.assertEqual(va["ledger_balance"], "1200.00")

    def test_selected_order_no_switches_detail(self):
        data = trace_fund(q="peter", selected_order_no="RMT_TRACE_002")
        self.assertEqual(data["order"]["order_no"], "RMT_TRACE_002")
        self.assertEqual(data["order"]["next_hop"]["code"], "awaiting_collection")
        self.assertEqual(data["match_count"], 3)

    def test_no_match_raises(self):
        with self.assertRaises(FundTraceNotFound):
            trace_fund(q="zzz-not-exist")


class FundTraceApiTests(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(
            merchant_name="Peter",
            status=Merchant.Status.ACTIVE,
        )
        expire = timezone.now() + timedelta(days=7)
        PaymentOrder.objects.create(
            order_no="RMT_API_001",
            merchant_order_no="M_API_001",
            unique_identification_no="UIN_API_001",
            idempotency_key="IDEM_API_001",
            merchant=self.merchant,
            amount=Decimal("1000.00"),
            currency="CNY",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("1.00"),
            settle_amount=Decimal("999.00"),
            status="COMPLETED",
            pay_method="WIRE_TRANSFER",
            beneficiary_name="ABC Company",
            beneficiary_bank="111111",
            expire_at=expire,
        )
        self.user = SystemUser.objects.create(
            username="trace_tester",
            password_hash="x",
            real_name="Tester",
        )
        role = Role.objects.create(
            code="super_admin", name="Fund Trace Super Admin"
        )
        UserRole.objects.create(user=self.user, role=role)
        self.factory = APIRequestFactory()

    def test_trace_fund_endpoint(self):
        request = self.factory.get("/api/v1/admin/orders/trace-fund/", {"q": "peter"})
        force_authenticate(request, user=self.user)
        view = PaymentOrderViewSet.as_view({"get": "trace_fund"})
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["match_count"], 1)
        self.assertEqual(response.data["order"]["next_hop"]["code"], "delivered_beneficiary")
        self.assertEqual(response.data["order"]["fee_amount"], "1.00")
