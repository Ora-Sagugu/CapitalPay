from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.merchant.models import Merchant
from apps.payment.models import PaymentOrder
from apps.user_portal.models import EndUser
from apps.user_portal.services import UserService


class MerchantRemittanceOverviewTests(TestCase):
    def setUp(self):
        self.svc = UserService()
        self.svc.register(phone="13900000991", password="Test@123", sms_code="")
        self.user = EndUser.objects.get(phone="13900000991")
        self.svc.choose_role(self.user, "merchant")
        self.user.refresh_from_db()
        self.merchant = Merchant.objects.create(
            merchant_no="OVW001",
            merchant_name="Overview Merch",
            status=Merchant.Status.ACTIVE,
        )
        self.user.default_merchant = self.merchant
        self.user.save(update_fields=["default_merchant"])
        self.client = APIClient()
        token = UserService._generate_token(str(self.user.id), user_type="user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _order(self, **kwargs):
        order_no = kwargs["order_no"]
        defaults = {
            "merchant_order_no": f"{order_no}_M",
            "unique_identification_no": f"UIN_{order_no}",
            "idempotency_key": f"IDEM_{order_no}",
            "merchant": self.merchant,
            "user_id": str(self.user.id),
            "amount": Decimal("100.00"),
            "currency": "USD",
            "from_currency": "USD",
            "to_currency": "CNY",
            "fee_amount": Decimal("5.00"),
            "settle_amount": Decimal("95.00"),
            "status": PaymentOrder.OrderStatus.PENDING_PAY,
            "expire_at": timezone.now(),
        }
        defaults.update(kwargs)
        return PaymentOrder.objects.create(**defaults)

    def test_overview_stats_by_period(self):
        self._order(order_no="RMT_OVW_OK", status=PaymentOrder.OrderStatus.SETTLED)
        self._order(order_no="RMT_OVW_FAIL", status=PaymentOrder.OrderStatus.CLOSED)
        old = self._order(order_no="RMT_OVW_OLD", status=PaymentOrder.OrderStatus.SETTLED)
        PaymentOrder.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=40),
        )

        month = self.svc.merchant_remittance_overview(self.user, period="month")
        self.assertEqual(month["period"], "month")
        self.assertEqual(month["remittance_count"], 2)
        self.assertEqual(month["success_count"], 1)
        self.assertEqual(month["success_rate"], "50.00")
        self.assertEqual(month["by_currency"][0]["currency"], "USD")
        self.assertEqual(month["by_currency"][0]["total_amount"], "200.00")
        self.assertEqual(month["by_currency"][0]["total_fee"], "10.00")

        all_time = self.svc.merchant_remittance_overview(self.user, period="all")
        self.assertEqual(all_time["remittance_count"], 3)
        self.assertEqual(all_time["success_count"], 2)
        self.assertEqual(all_time["success_rate"], "66.67")

        response = self.client.get("/api/v1/user/payments/remittances/stats/", {"period": "all"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["remittance_count"], 3)
        self.assertEqual(response.data["success_rate"], "66.67")


class MerchantCustomerCreateTests(TestCase):
    def setUp(self):
        self.svc = UserService()
        self.svc.register(phone="13900000992", password="Test@123", sms_code="")
        self.user = EndUser.objects.get(phone="13900000992")
        self.svc.choose_role(self.user, "merchant")
        self.user.refresh_from_db()
        self.merchant = Merchant.objects.create(
            merchant_no="CUS001",
            merchant_name="Customer Merch",
            status=Merchant.Status.ACTIVE,
        )
        self.user.default_merchant = self.merchant
        self.user.onboarding_status = "approved"
        self.user.save(update_fields=["default_merchant", "onboarding_status"])

    def test_create_customer_is_approved_not_draft(self):
        from apps.agent.models import AgentCustomer

        row = self.svc.create_merchant_customer(self.user, {"legal_name": "Buyer Co"})
        self.assertEqual(row["kyc_status"], AgentCustomer.KycStatus.APPROVED)
        self.assertEqual(row["legal_name"], "Buyer Co")
        updated = self.svc.update_merchant_customer(self.user, row["id"], {"nationality": "KE"})
        self.assertEqual(updated["nationality"], "KE")
        self.assertEqual(updated["kyc_status"], AgentCustomer.KycStatus.APPROVED)

    def test_merchant_can_delete_own_customer(self):
        from apps.agent.models import AgentCustomer
        from apps.core.exceptions import BusinessException

        row = self.svc.create_merchant_customer(self.user, {"legal_name": "Buyer Co"})
        self.svc.delete_merchant_customer(self.user, row["id"])
        customer = AgentCustomer.objects.get(pk=row["id"])
        self.assertTrue(customer.is_deleted)
        listed = self.svc.list_bound_merchant_customers(self.user)
        self.assertEqual(listed, [])
        with self.assertRaises(BusinessException) as ctx:
            self.svc.delete_merchant_customer(self.user, row["id"])
        self.assertEqual(ctx.exception.code, "CUSTOMER_NOT_FOUND")

        client = APIClient()
        token = UserService._generate_token(str(self.user.id), user_type="user")
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        remaining = self.svc.create_merchant_customer(self.user, {"legal_name": "Second Co"})
        response = client.delete(f"/api/v1/user/customers/{remaining['id']}/")
        self.assertEqual(response.status_code, 204)
        self.assertTrue(AgentCustomer.objects.get(pk=remaining["id"]).is_deleted)


class MerchantRemittanceCustomerApiTests(TestCase):
    def setUp(self):
        from apps.payment.tests_remittance_v2 import create_eligible_merchant

        self.svc = UserService()
        self.svc.register(phone="13900000993", password="Test@123", sms_code="")
        self.user = EndUser.objects.get(phone="13900000993")
        self.svc.choose_role(self.user, "merchant")
        self.user.refresh_from_db()
        self.merchant = create_eligible_merchant("MCQ")
        self.user.default_merchant = self.merchant
        self.user.onboarding_status = "approved"
        self.user.save(update_fields=["default_merchant", "onboarding_status"])
        self.client = APIClient()
        token = UserService._generate_token(str(self.user.id), user_type="user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.customer = self.svc.create_merchant_customer(self.user, {"legal_name": "Buyer Co"})

    def test_quote_without_customer_id_asks_to_select_customer(self):
        res = self.client.post(
            "/api/v1/user/payments/quote/",
            {"amount": "100.00", "from_currency": "USD", "to_currency": "USD", "fee_bearing": "OUR"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["code"], "CUSTOMER_REQUIRED")

    def test_quote_and_apply_bind_the_selected_customer(self):
        quote = self.client.post(
            "/api/v1/user/payments/quote/",
            {
                "customer_id": self.customer["id"],
                "amount": "100.00",
                "from_currency": "USD",
                "to_currency": "USD",
                "fee_bearing": "OUR",
            },
            format="json",
        )
        self.assertEqual(quote.status_code, 201, quote.content)
        self.assertEqual(quote.data["customer_id"], self.customer["id"])

        applied = self.client.post(
            "/api/v1/user/payments/apply/",
            {
                "customer_id": self.customer["id"],
                "quote_id": quote.data["quote_id"],
                "beneficiary_name": "Supplier Co",
                "beneficiary_bank": "Bank",
                "beneficiary_account": "998877",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="idem-mcq-ok",
        )
        self.assertEqual(applied.status_code, 201, applied.content)
        order = PaymentOrder.objects.get(order_no=applied.data["order_no"])
        self.assertEqual(str(order.agent_customer_id), self.customer["id"])


class MerchantRefundApplyApiTests(TestCase):
    def setUp(self):
        self.svc = UserService()
        self.svc.register(phone="13900000994", password="Test@123", sms_code="")
        self.user = EndUser.objects.get(phone="13900000994")
        self.svc.choose_role(self.user, "merchant")
        self.user.refresh_from_db()
        self.merchant = Merchant.objects.create(
            merchant_no="RFD001",
            merchant_name="Refund Merch",
            status=Merchant.Status.ACTIVE,
        )
        self.user.default_merchant = self.merchant
        self.user.onboarding_status = "approved"
        self.user.save(update_fields=["default_merchant", "onboarding_status"])
        self.client = APIClient()
        token = UserService._generate_token(str(self.user.id), user_type="user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _order(self, **kwargs):
        order_no = kwargs["order_no"]
        defaults = {
            "merchant_order_no": f"{order_no}_M",
            "unique_identification_no": f"UIN_{order_no}",
            "idempotency_key": f"IDEM_{order_no}",
            "merchant": self.merchant,
            "user_id": str(self.user.id),
            "amount": Decimal("100.00"),
            "currency": "USD",
            "from_currency": "USD",
            "to_currency": "CNY",
            "fee_amount": Decimal("5.00"),
            "settle_amount": Decimal("95.00"),
            "status": PaymentOrder.OrderStatus.PAY_RECEIVED,
            "expire_at": timezone.now(),
        }
        defaults.update(kwargs)
        return PaymentOrder.objects.create(**defaults)

    def test_merchant_refund_apply_appears_as_pending_review(self):
        from apps.payment.models import RefundOrder

        order = self._order(order_no="RMT_RFD_OK")
        response = self.client.post(
            "/api/v1/user/payments/refund-apply/",
            {"order_no": order.order_no, "reason": "Goods returned"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["status"], RefundOrder.RefundStatus.PENDING_REVIEW)
        refund = RefundOrder.objects.get(refund_no=response.data["refund_no"])
        self.assertEqual(refund.payment_order_id, order.id)
        self.assertEqual(refund.refund_amount, Decimal("100.00"))
        self.assertEqual(refund.refund_reason, "Goods returned")
        order.refresh_from_db()
        self.assertEqual(order.status, PaymentOrder.OrderStatus.REFUNDING)
