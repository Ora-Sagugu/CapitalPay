"""手册对齐补齐 — 执照限制 / AgentKYC / 退款 PRN 搜索。"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.agent.models import Agent, AgentKYC
from apps.merchant.models import Merchant
from apps.merchant.tasks import suspend_expired_licenses
from apps.payment.models import PaymentOrder, RefundOrder
from apps.payment.serializers import RemittanceApplySerializer
from apps.payment.views import RefundOrderViewSet
from apps.rbac.models import SystemUser


class LicenseRestrictTests(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(
            merchant_name="License Test Co",
            status=Merchant.Status.ACTIVE,
            fee_rate=Decimal("0.1"),
            fixed_fee=Decimal("1"),
            license_expiry_date=date.today() - timedelta(days=1),
        )

    def test_suspend_expired_licenses_task(self):
        result = suspend_expired_licenses()
        self.merchant.refresh_from_db()
        self.assertEqual(self.merchant.status, Merchant.Status.SUSPENDED)
        self.assertGreaterEqual(result["suspended"], 1)

    def test_remittance_apply_blocks_expired_license(self):
        from rest_framework.exceptions import ValidationError
        ser = RemittanceApplySerializer(data={
            "merchant": self.merchant.merchant_no,
            "from_currency": "USD",
            "to_currency": "CNY",
            "amount": "100",
            "pay_method": "WIRE_TRANSFER",
            "beneficiary_name": "Alice",
            "beneficiary_bank": "Bank",
            "beneficiary_account": "123",
        })
        self.assertTrue(ser.is_valid(), ser.errors)
        with self.assertRaises(ValidationError):
            ser.save()


class AgentKYCApiTests(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(
            agent_no="A_TEST_001",
            agent_name="Agent KYC Test",
            status="PENDING",
        )

    def test_create_and_approve_kyc(self):
        kyc = AgentKYC.objects.create(
            agent=self.agent,
            legal_person="Zhang",
            id_number="X",
            id_number_plain="110101199001011234",
            business_license="BL001",
        )
        kyc.submit()
        kyc.approve(reviewer="admin", comment="ok")
        self.assertEqual(kyc.kyc_status, AgentKYC.KycStatus.APPROVED)


class RefundPrnSearchTests(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(
            merchant_name="Refund Search Co",
            status=Merchant.Status.ACTIVE,
        )
        self.order = PaymentOrder.objects.create(
            order_no="RMT_TEST_PRN_001",
            merchant_order_no="M_TEST_001",
            unique_identification_no="UIN001",
            idempotency_key="IDEM_PRN_001",
            merchant=self.merchant,
            amount=Decimal("100"),
            currency="USD",
            fee_amount=Decimal("1"),
            settle_amount=Decimal("99"),
            status="PENDING_PAY",
            prn_code="PRN_SEARCH_XYZ",
            expire_at=date.today() + timedelta(days=7),
        )
        self.refund = RefundOrder.objects.create(
            refund_no="RF_TEST_001",
            payment_order=self.order,
            refund_amount=Decimal("50"),
            refund_fee_rate=Decimal("0"),
            refund_fee_amount=Decimal("0"),
            refund_reason="test",
            status="PENDING_REVIEW",
        )
        self.user = SystemUser.objects.create(
            username="refund_tester",
            password_hash="x",
            real_name="Tester",
        )

    def test_search_by_prn(self):
        factory = APIRequestFactory()
        request = factory.get("/api/v1/admin/refunds/", {"search": "PRN_SEARCH_XYZ"})
        force_authenticate(request, user=self.user)
        view = RefundOrderViewSet.as_view({"get": "list"})
        response = view(request)
        self.assertEqual(response.status_code, 200)
        data = response.data
        results = data.get("results", data if isinstance(data, list) else [])
        self.assertTrue(any(r.get("refund_no") == "RF_TEST_001" for r in results))
