"""Bank credit notification matching and mock ingest APIs."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.merchant.services import ensure_merchant_currency_account
from apps.payment.models import BankCreditNotification, PaymentOrder
from apps.payment.services.bank_notification import ingest_credit, simulate_credit
from apps.payment.tests_remittance_v2 import create_eligible_merchant
from apps.rbac.models import SystemUser
from apps.rbac.testing import attach_super_admin


def _expire():
    return timezone.now() + timedelta(days=7)


class BankCreditNotificationServiceTests(TestCase):
    def setUp(self):
        self.merchant = create_eligible_merchant("BN")
        ensure_merchant_currency_account(self.merchant, "USD")
        self.order = PaymentOrder.objects.create(
            order_no="RMT_BN_001",
            merchant_order_no="M_BN_001",
            unique_identification_no="UIN_BN_001",
            idempotency_key="IDEM_BN_001",
            merchant=self.merchant,
            prn_code="A25503",
            amount=Decimal("10000.00"),
            currency="USD",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("32.00"),
            settle_amount=Decimal("9968.00"),
            status=PaymentOrder.OrderStatus.PENDING_PAY,
            pay_method=PaymentOrder.PayMethod.WIRE_TRANSFER,
            beneficiary_name="Payee",
            expire_at=_expire(),
        )

    def test_match_prn_from_remark(self):
        note = ingest_credit(
            amount="10000.00",
            currency="usd",
            remark="please credit PRN:A25503",
        )
        self.assertEqual(note.status, BankCreditNotification.Status.MATCHED)
        self.assertEqual(note.prn_code, "A25503")
        self.assertEqual(note.order_no, self.order.order_no)
        self.assertEqual(note.merchant_no, self.merchant.merchant_no)
        self.assertEqual(note.merchant_name, self.merchant.merchant_name)
        self.assertTrue(note.bank_name)
        self.assertTrue(note.account_no)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, PaymentOrder.OrderStatus.PENDING_PAY)

    def test_amount_mismatch(self):
        note = ingest_credit(
            amount=Decimal("9999.00"),
            currency="USD",
            prn_code="A25503",
        )
        self.assertEqual(note.status, BankCreditNotification.Status.MISMATCH)
        self.assertEqual(note.order_id, self.order.id)

    def test_unknown_prn_is_unmatched(self):
        note = ingest_credit(
            amount="50.00",
            currency="USD",
            remark="PRN:A00101",
        )
        self.assertEqual(note.status, BankCreditNotification.Status.UNMATCHED)
        self.assertEqual(note.prn_code, "A00101")
        self.assertEqual(note.order_no, "")

    def test_no_prn_is_unmatched(self):
        note = ingest_credit(
            amount="1500.00",
            currency="USD",
            remark="WALK-IN CASH / NO PRN",
        )
        self.assertEqual(note.status, BankCreditNotification.Status.UNMATCHED)
        self.assertEqual(note.prn_code, "")

    def test_same_txn_id_is_idempotent(self):
        first = ingest_credit(
            amount="10000.00",
            currency="USD",
            prn_code="A25503",
            txn_id="BNK-DUP-1",
        )
        second = ingest_credit(
            amount="1.00",
            currency="USD",
            prn_code="A25503",
            txn_id="BNK-DUP-1",
        )
        self.assertEqual(first.id, second.id)
        self.assertEqual(BankCreditNotification.objects.filter(txn_id="BNK-DUP-1").count(), 1)
        self.assertEqual(Decimal(second.amount), Decimal("10000.00"))

    def test_simulate_fills_amount_from_order(self):
        note = simulate_credit({"prn_code": "A25503"})
        self.assertEqual(note.status, BankCreditNotification.Status.MATCHED)
        self.assertEqual(note.amount, Decimal("10000.00"))
        self.assertEqual(note.currency, "USD")
        self.assertEqual(note.source, BankCreditNotification.Source.MOCK)


class BankCreditNotificationApiTests(TestCase):
    def setUp(self):
        self.merchant = create_eligible_merchant("BA")
        ensure_merchant_currency_account(self.merchant, "USD")
        self.order = PaymentOrder.objects.create(
            order_no="RMT_BN_API",
            merchant_order_no="M_BN_API",
            unique_identification_no="UIN_BN_API",
            idempotency_key="IDEM_BN_API",
            merchant=self.merchant,
            prn_code="B10001",
            amount=Decimal("250.00"),
            currency="USD",
            from_currency="USD",
            to_currency="EUR",
            fee_amount=Decimal("2.00"),
            settle_amount=Decimal("248.00"),
            status=PaymentOrder.OrderStatus.PENDING_PAY,
            pay_method=PaymentOrder.PayMethod.WIRE_TRANSFER,
            beneficiary_name="Payee",
            expire_at=_expire(),
        )
        self.client = APIClient()
        operator = SystemUser.objects.create(
            username="bank-notify-ops",
            password_hash="test",
            real_name="Bank Notify Operator",
        )
        attach_super_admin(operator)
        self.client.force_authenticate(operator)

    def test_simulate_list_and_stats(self):
        created = self.client.post(
            "/api/v1/admin/bank-notifications/simulate/",
            {"prn_code": "B10001", "txn_id": "BNK-API-1"},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["status"], "MATCHED")
        self.assertEqual(created.data["order_no"], "RMT_BN_API")
        self.assertEqual(created.data["merchant_name"], self.merchant.merchant_name)

        replay = self.client.post(
            "/api/v1/admin/bank-notifications/simulate/",
            {"prn_code": "B10001", "txn_id": "BNK-API-1", "amount": "1.00"},
            format="json",
        )
        self.assertEqual(replay.status_code, 201)
        self.assertEqual(replay.data["notification_no"], created.data["notification_no"])
        self.assertEqual(BankCreditNotification.objects.count(), 1)

        listed = self.client.get("/api/v1/admin/bank-notifications/", {"search": "B10001"})
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.data["count"], 1)
        row = listed.data["results"][0]
        self.assertEqual(row["prn_code"], "B10001")
        self.assertTrue(row["bank_name"])

        detail = self.client.get(
            f"/api/v1/admin/bank-notifications/{created.data['notification_no']}/"
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["order_status"], PaymentOrder.OrderStatus.PENDING_PAY)
        self.assertEqual(detail.data["expected_amount"], "250.00")

        stats = self.client.get("/api/v1/admin/bank-notifications/stats/")
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.data["total_count"], 1)
        self.assertEqual(stats.data["matched"], 1)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, PaymentOrder.OrderStatus.PENDING_PAY)

    def test_mismatch_filter(self):
        self.client.post(
            "/api/v1/admin/bank-notifications/simulate/",
            {"prn_code": "B10001", "amount": "10.00", "currency": "USD"},
            format="json",
        )
        listed = self.client.get("/api/v1/admin/bank-notifications/", {"status": "MISMATCH"})
        self.assertEqual(listed.data["count"], 1)
        self.assertEqual(listed.data["results"][0]["status"], "MISMATCH")
