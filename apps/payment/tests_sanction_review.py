"""Read-only order sanctions screening for the admin Orders page."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.compliance.models import SanctionList, SanctionScanRecord
from apps.merchant.models import Merchant
from apps.payment.models import PaymentOrder
from apps.payment.views import PaymentOrderViewSet
from apps.rbac.models import Role, SystemUser, UserRole


class OrderSanctionReviewApiTests(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(
            merchant_name="Screening Customer",
            status=Merchant.Status.ACTIVE,
            sanction_status="UN",
        )
        expire = timezone.now() + timedelta(days=7)
        self.clear_order = PaymentOrder.objects.create(
            order_no="RMT_SCR_CLEAR",
            merchant_order_no="M_SCR_CLEAR",
            unique_identification_no="UIN_SCR_CLEAR",
            idempotency_key="IDEM_SCR_CLEAR",
            merchant=self.merchant,
            amount=Decimal("1000.00"),
            currency="CNY",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("1.00"),
            settle_amount=Decimal("999.00"),
            status="PENDING_REVIEW",
            pay_method="WIRE_TRANSFER",
            beneficiary_name="ACME Supplier",
            beneficiary_address="1 Main Street, London",
            expire_at=expire,
        )
        self.hit_order = PaymentOrder.objects.create(
            order_no="RMT_SCR_HIT",
            merchant_order_no="M_SCR_HIT",
            unique_identification_no="UIN_SCR_HIT",
            idempotency_key="IDEM_SCR_HIT",
            merchant=self.merchant,
            amount=Decimal("1000.00"),
            currency="CNY",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("1.00"),
            settle_amount=Decimal("999.00"),
            status="PENDING_REVIEW",
            pay_method="WIRE_TRANSFER",
            beneficiary_name="SANCTIONED PERSON",
            beneficiary_address="1 Main Street, London",
            expire_at=expire,
        )
        SanctionList.objects.create(
            entity_name="SANCTIONED PERSON",
            list_type="OFAC",
            risk_level="HIGH",
            is_active=True,
        )
        self.user = SystemUser.objects.create(
            username="screening_tester",
            password_hash="x",
            real_name="Tester",
        )
        role = Role.objects.create(code="super_admin", name="Screening Super Admin")
        UserRole.objects.create(user=self.user, role=role)
        self.factory = APIRequestFactory()

    def _get_review(self, order_no):
        request = self.factory.get(f"/api/v1/admin/orders/{order_no}/sanction-review/")
        force_authenticate(request, user=self.user)
        view = PaymentOrderViewSet.as_view({"get": "sanction_review"})
        return view(request, order_no=order_no)

    def test_clear_order_returns_no_hits(self):
        response = self._get_review("RMT_SCR_CLEAR")
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(data["order_no"], "RMT_SCR_CLEAR")
        self.assertTrue(data["is_clear"])
        self.assertFalse(data["blocked"])
        self.assertEqual(data["total_hits"], 0)
        self.assertEqual(data["name_hits"], [])
        self.assertEqual(data["address_hits"], [])
        self.assertEqual(data["country_hits"], [])
        self.assertEqual(data["warning_message"], "")
        self.assertEqual(data["screened"]["beneficiary_name"], "ACME Supplier")
        self.assertEqual(data["screened"]["customer_name"], "Screening Customer")
        self.assertEqual(data["screened"]["customer_sanction_status"], "UN")
        self.assertEqual(SanctionScanRecord.objects.count(), 0)

    def test_exact_high_risk_name_hit_is_blocked_flag_only(self):
        response = self._get_review("RMT_SCR_HIT")
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(data["order_no"], "RMT_SCR_HIT")
        self.assertFalse(data["is_clear"])
        self.assertTrue(data["blocked"])
        self.assertGreater(data["total_hits"], 0)
        self.assertTrue(data["name_hits"])
        self.assertEqual(data["name_hits"][0]["entity_name"], "SANCTIONED PERSON")
        self.assertEqual(data["name_hits"][0]["list_type"], "OFAC")
        self.assertEqual(data["name_hits"][0]["match_type"], "exact_name")
        self.assertTrue(data["warning_message"])
        self.assertEqual(PaymentOrder.objects.get(order_no="RMT_SCR_HIT").status, "PENDING_REVIEW")
        self.assertEqual(SanctionScanRecord.objects.count(), 0)
