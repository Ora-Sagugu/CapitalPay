"""经营分析契约、权限、脱敏与资金闭环测试。"""
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.account.models import MoneyMovement, NostroAccount, VaLedgerEntry, VirtualAccount
from apps.agent.models import Agent
from apps.merchant.models import Merchant
from apps.payment.gateway import BankGatewayRouter
from apps.payment.models import PaymentOrder, RefundOrder
from apps.payment.services.payment import PaymentConfirmService
from apps.payment.services.refund import RefundService
from apps.rbac.models import Permission, Role, RolePermission, SystemUser, UserRole, OperationLog
from apps.rbac.services import AuthService
from apps.report.analytics import breakdowns, parse_filters, summary, transactions
from apps.report.metrics import mask_account, money_str
from apps.settlement.engine.batch_creator import SettlementBatchCreator
from apps.settlement.engine.distributor import FundsDistributor
from apps.settlement.models import SettlementBatch
from apps.user_portal.models import EndUser


TZ = ZoneInfo("Africa/Nairobi")


def _aware(day, hour=10, minute=0):
    return datetime.combine(day, time(hour, minute), tzinfo=TZ)


class AnalyticsHelpers:
    def _merchant(self, **kwargs):
        defaults = dict(merchant_name="Acme", status=Merchant.Status.ACTIVE)
        defaults.update(kwargs)
        return Merchant.objects.create(**defaults)

    def _order(self, merchant, *, amount="100.00", currency="USD", status="PENDING_REVIEW", **kwargs):
        n = PaymentOrder.objects.count() + 1
        payload = dict(
            order_no=f"P_AN_{n:04d}",
            merchant_order_no=f"M_AN_{n:04d}",
            unique_identification_no=f"UIN_AN_{n:04d}",
            idempotency_key=f"IDEM_AN_{n:04d}",
            merchant=merchant,
            amount=Decimal(amount),
            currency=currency,
            from_currency=currency,
            to_currency="KES",
            fee_amount=Decimal("1.00"),
            settle_amount=Decimal(amount) - Decimal("1.00"),
            status=status,
            pay_method="WIRE_TRANSFER",
            bank_code="MOCK",
            expire_at=timezone.now() + timedelta(days=2),
        )
        payload.update(kwargs)
        return PaymentOrder.objects.create(**payload)

    def _grant(self, user, *codes):
        role, _ = Role.objects.get_or_create(code="analyst", defaults={"name": "Analyst"})
        UserRole.objects.get_or_create(user=user, role=role)
        for code in codes:
            perm, _ = Permission.objects.get_or_create(
                code=code, defaults={"name": code, "resource": "report", "action": code.split(":")[-1]},
            )
            RolePermission.objects.get_or_create(role=role, permission=perm)


class MetricContractTests(AnalyticsHelpers, TestCase):
    def setUp(self):
        self.merchant = self._merchant()
        self.day = timezone.localdate()

    def test_multi_currency_is_not_summed(self):
        o1 = self._order(self.merchant, amount="100.00", currency="USD")
        o2 = self._order(self.merchant, amount="200.00", currency="KES")
        PaymentOrder.objects.filter(pk=o1.pk).update(created_at=_aware(self.day, 9))
        PaymentOrder.objects.filter(pk=o2.pk).update(created_at=_aware(self.day, 10))
        data = summary(parse_filters({
            "date_from": str(self.day), "date_to": str(self.day), "time_basis": "created_at",
        }))
        currencies = {row["currency"]: row for row in data["application"]["by_currency"]}
        self.assertEqual(currencies["USD"]["amount"], "100.00")
        self.assertEqual(currencies["KES"]["amount"], "200.00")
        self.assertEqual(data["application"]["count"], 2)
        self.assertFalse(data["contract"]["cross_currency_sum"])

    def test_nairobi_day_boundary(self):
        start = datetime.combine(self.day, time.min, tzinfo=TZ)
        before = start - timedelta(microseconds=1)
        on_day = start
        o1 = self._order(self.merchant, amount="10.00")
        o2 = self._order(self.merchant, amount="20.00")
        PaymentOrder.objects.filter(pk=o1.pk).update(created_at=before)
        PaymentOrder.objects.filter(pk=o2.pk).update(created_at=on_day)
        data = summary(parse_filters({
            "date_from": str(self.day), "date_to": str(self.day),
        }))
        self.assertEqual(data["application"]["count"], 1)
        self.assertEqual(data["application"]["by_currency"][0]["amount"], "20.00")

    def test_unlinked_user_coverage(self):
        self._order(self.merchant, user_id="u-1")
        self._order(self.merchant, user_id="")
        PaymentOrder.objects.update(created_at=_aware(self.day, 12))
        data = summary(parse_filters({"date_from": str(self.day), "date_to": str(self.day)}))
        self.assertEqual(data["coverage"]["user_id"]["linked"], 1)
        self.assertEqual(data["coverage"]["user_id"]["unlinked"], 1)
        rows = breakdowns(parse_filters({
            "date_from": str(self.day), "date_to": str(self.day), "dimension": "user",
        }))["rows"]
        labels = {r["label"] for r in rows}
        self.assertIn("Unlinked user", labels)

    def test_refund_and_pending_aging(self):
        order = self._order(self.merchant, status="PAY_RECEIVED")
        PaymentOrder.objects.filter(pk=order.pk).update(
            created_at=_aware(self.day, 8),
            pay_received_at=_aware(self.day, 9),
        )
        RefundOrder.objects.create(
            refund_no="R_AN_1",
            payment_order=order,
            refund_amount=Decimal("10.00"),
            refund_reason="test",
            status=RefundOrder.RefundStatus.SUCCESS,
            refunded_at=_aware(self.day, 11),
        )
        data = summary(parse_filters({"date_from": str(self.day), "date_to": str(self.day)}))
        self.assertEqual(data["successful_refunds"]["count"], 1)
        self.assertEqual(data["successful_refunds"]["by_currency"][0]["amount"], "10.00")

    def test_mask_and_page_totals_match_summary(self):
        self._order(self.merchant, amount="30.00", beneficiary_account="1234567890")
        PaymentOrder.objects.update(created_at=_aware(self.day, 12))
        filters = parse_filters({"date_from": str(self.day), "date_to": str(self.day), "page": 1, "page_size": 20})
        s = summary(filters)
        t = transactions(filters)
        self.assertEqual(t["count"], s["application"]["count"])
        self.assertEqual(t["page_totals"]["by_currency"][0]["amount"], s["application"]["by_currency"][0]["amount"])
        self.assertEqual(t["results"][0]["beneficiary_account"], mask_account("1234567890"))
        self.assertEqual(money_str("1.2"), "1.20")


class AnalyticsApiPermissionTests(AnalyticsHelpers, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.svc = AuthService()
        self.user = SystemUser.objects.create(
            username="fin1", password_hash=self.svc._hash_password("Secret@123"), real_name="Fin",
        )
        self._grant(self.user, "feature:reports")
        self.token = self.svc._generate_token(str(self.user.id), user_type="admin")
        self.merchant = self._merchant()
        order = self._order(self.merchant, amount="50.00", beneficiary_account="9988776655")
        PaymentOrder.objects.filter(pk=order.pk).update(created_at=_aware(timezone.localdate(), 10))
        self.day = str(timezone.localdate())

    def _auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_system_user_can_query(self):
        self._auth(self.token)
        res = self.client.get("/api/v1/admin/reports/analytics/summary/", {"date_from": self.day, "date_to": self.day})
        self.assertEqual(res.status_code, 200)
        self.assertIn("by_currency", res.data["application"])

    def test_end_user_forbidden(self):
        end = EndUser.objects.create(username="c1", email="c1@example.com", password_hash="x")
        token = self.svc._generate_token(str(end.id), user_type="user")
        self._auth(token)
        res = self.client.get("/api/v1/admin/reports/analytics/summary/", {"date_from": self.day, "date_to": self.day})
        self.assertEqual(res.status_code, 403)

    def test_missing_view_permission(self):
        other = SystemUser.objects.create(
            username="ops_no", password_hash=self.svc._hash_password("Secret@123"), real_name="Ops",
        )
        token = self.svc._generate_token(str(other.id), user_type="admin")
        self._auth(token)
        res = self.client.get("/api/v1/admin/reports/analytics/summary/", {"date_from": self.day, "date_to": self.day})
        self.assertEqual(res.status_code, 403)

    def test_export_writes_operation_log(self):
        self._auth(self.token)
        res = self.client.post(
            "/api/v1/admin/reports/analytics/export/",
            {"date_from": self.day, "date_to": self.day},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("spreadsheetml", res["Content-Type"])
        log = OperationLog.objects.filter(action=OperationLog.ActionType.EXPORT, resource="report").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.detail.get("row_count"), 1)


@override_settings(BANK_GATEWAY_MODE="MOCK", BANK_CODES=["MOCK"])
class MoneyMovementLifecycleTests(AnalyticsHelpers, TestCase):
    def setUp(self):
        BankGatewayRouter._bootstrapped = False
        BankGatewayRouter._gateways = {}
        self.merchant = self._merchant()
        self.master = NostroAccount.objects.create(
            merchant=self.merchant,
            account_no="NOS_AN_1",
            bank_code="MOCK",
            bank_name="Mock",
            account_number="111",
            currency="USD",
            balance=Decimal("0.00"),
        )
        self.va = VirtualAccount.objects.create(
            master_account=self.master,
            merchant=self.merchant,
            va_number="VAV_AN_1",
            va_type=VirtualAccount.VaType.VAV,
            bank_code="MOCK",
            bank_name="Mock",
            account_holder="Acme",
            currency="USD",
            ledger_balance=Decimal("0.00"),
            available_balance=Decimal("0.00"),
        )

    def test_confirm_writes_movement_and_payout_settles_only_after_bank_success(self):
        order = self._order(self.merchant, status="PENDING_PAY", amount="80.00", currency="USD")
        PaymentConfirmService()._confirm_payment(order, {"txn_id": "BNK1", "amount": Decimal("80.00")})
        order.refresh_from_db()
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PAY_RECEIVED)
        self.assertTrue(MoneyMovement.objects.filter(
            payment_order=order, movement_type=MoneyMovement.MovementType.COLLECTION
        ).exists())
        self.assertTrue(VaLedgerEntry.objects.filter(order=order, entry_type="CREDIT").exists())

        order.status = PaymentOrder.OrderStatus.PENDING_SETTLE
        order.save(update_fields=["status"])
        settle_date = timezone.localtime(order.pay_received_at).date()
        batches = SettlementBatchCreator().create_daily_batches(settle_date)
        self.assertEqual(len(batches), 1)
        order.refresh_from_db()
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PENDING_SETTLE)

        FundsDistributor().distribute(batches[0])
        order.refresh_from_db()
        batches[0].refresh_from_db()
        self.assertEqual(batches[0].status, SettlementBatch.SettleStatus.SETTLED)
        self.assertTrue(batches[0].bank_txn_id)
        self.assertEqual(order.status, PaymentOrder.OrderStatus.SETTLED)
        payout = MoneyMovement.objects.get(settlement_batch=batches[0], movement_type="SETTLEMENT_PAYOUT")
        self.assertEqual(payout.status, MoneyMovement.MovementStatus.SUCCESS)
        self.assertEqual(payout.evidence_level, MoneyMovement.EvidenceLevel.BANK_CONFIRMED)
        with self.assertRaises(RuntimeError):
            payout.remark = "tamper"
            payout.save()

    def test_refund_writes_reverse_movement(self):
        order = self._order(self.merchant, status="PENDING_PAY", amount="40.00")
        PaymentConfirmService()._confirm_payment(order, {"txn_id": "BNK2", "amount": Decimal("40.00")})
        order.refresh_from_db()
        refund = RefundService().request_refund(
            payment_order=order, refund_amount=Decimal("40.00"), reason="all"
        )
        RefundService().execute_refund(refund)
        refund.refresh_from_db()
        self.assertEqual(refund.status, RefundOrder.RefundStatus.SUCCESS)
        self.assertTrue(MoneyMovement.objects.filter(
            refund_order=refund, movement_type=MoneyMovement.MovementType.REFUND
        ).exists())
        self.assertTrue(VaLedgerEntry.objects.filter(source_type="REFUND", entry_type="DEBIT").exists())
