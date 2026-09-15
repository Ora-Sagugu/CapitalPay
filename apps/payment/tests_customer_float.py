from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.account.models import NostroAccount, VaLedgerEntry, VirtualAccount
from apps.account.services import AccountService
from apps.agent.models import Agent
from apps.agent.services import get_agent_ledger_va
from apps.merchant.services import ensure_merchant_virtual_account
from apps.payment.models import PaymentOrder
from apps.payment.services.payment import PaymentConfirmService
from apps.payment.services.remittance_application import RemittanceApplicationService
from apps.payment.services.remittance_quote import RemittanceQuoteService
from apps.payment.tests_remittance_v2 import (
    create_eligible_merchant,
    ensure_global_remittance_fee,
    submit_payload,
)
from apps.payment.views import PaymentOrderViewSet
from apps.rbac.models import SystemUser
from apps.rbac.testing import attach_super_admin
from apps.routing.models import BankChannel


class CustomerRemittanceFloatTests(TestCase):
    def setUp(self):
        self.merchant = create_eligible_merchant(
            "FL",
            max_single=Decimal("50000"),
            daily_limit=Decimal("100000"),
        )
        ensure_global_remittance_fee(
            fixed_fee=Decimal("100.00"),
            percent_rate=Decimal("0"),
            max_fee=Decimal("100.00"),
        )
        self.agent = Agent.objects.create(
            agent_no="AG_FLOAT_01",
            agent_name="Float Agent",
            status="ACTIVE",
        )
        self.merchant.agent = self.agent
        self.merchant.save(update_fields=["agent", "updated_at"])
        self.ops = SystemUser.objects.create(
            username="ops_float",
            password_hash="x",
            real_name="Ops Float",
        )
        attach_super_admin(self.ops)
        self.factory = APIRequestFactory()
        BankChannel.objects.create(
            bank_code="MID",
            bank_name="Mid Bank",
            fee_rate=Decimal("0.002"),
            min_fee=Decimal("1.00"),
            max_fee=Decimal("500.00"),
            usd_balance=Decimal("50000.00"),
            priority=1,
        )

    def _quote_and_submit(self, amount="10000"):
        quote = RemittanceQuoteService().create_quote(
            merchant=self.merchant,
            amount=amount,
            from_currency="USD",
            to_currency="USD",
            fee_bearing="OUR",
            actor_type="ADMIN",
        )
        order, _ = RemittanceApplicationService().submit(
            merchant=self.merchant,
            payload=submit_payload(quote),
            idempotency_key=f"idem-float-{amount}",
            user_id="user-float",
            actor_type="ADMIN",
        )
        return order

    def _call(self, method, action, order_no, data=None):
        path = f"/api/v1/admin/orders/{order_no}/{action.replace('_', '-')}/"
        if method == "get":
            request = self.factory.get(path)
        else:
            request = self.factory.post(path, data or {}, format="json")
        force_authenticate(request, user=self.ops)
        return PaymentOrderViewSet.as_view({method: action})(request, order_no=order_no)

    def _usd_va(self):
        return VirtualAccount.objects.filter(
            merchant=self.merchant,
            currency="USD",
            is_deleted=False,
        ).first()

    def test_confirm_payment_credits_principal_not_fee(self):
        order = self._quote_and_submit()
        self.assertEqual(order.amount, Decimal("10000.00"))
        self.assertEqual(order.fee_amount, Decimal("100.00"))
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PENDING_REVIEW)

        approved = self._call("post", "review_remittance", order.order_no, {"action": "approve"})
        self.assertEqual(approved.status_code, 200, getattr(approved, "data", approved))

        credited = self._call("post", "confirm_payment", order.order_no)
        self.assertEqual(credited.status_code, 200, getattr(credited, "data", credited))
        order.refresh_from_db()
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PAY_RECEIVED)

        va = self._usd_va()
        self.assertIsNotNone(va)
        self.assertEqual(va.ledger_balance, Decimal("10000.00"))
        self.assertEqual(va.available_balance, Decimal("10000.00"))
        self.assertFalse(
            VirtualAccount.objects.filter(
                merchant=self.merchant, currency="CNY", is_deleted=False,
            ).exists()
        )
        fee_va = get_agent_ledger_va(self.agent, NostroAccount.AccountType.FEE, "USD")
        self.assertIsNotNone(fee_va)
        self.assertEqual(fee_va.ledger_balance, Decimal("100.00"))

    def test_confirm_transfer_clears_customer_balance_and_settlement_is_idempotent(self):
        order = self._quote_and_submit()
        self._call("post", "review_remittance", order.order_no, {"action": "approve"})
        self._call("post", "confirm_payment", order.order_no)
        order.refresh_from_db()
        self.assertEqual(
            order.agent_payout_request_status,
            PaymentOrder.AgentPayoutRequestStatus.PENDING,
        )
        RemittanceApplicationService().request_payout_by_agent(order, reviewer="agent-float")

        transferred = self._call("post", "confirm_transfer", order.order_no)
        self.assertEqual(transferred.status_code, 200, getattr(transferred, "data", transferred))
        order.refresh_from_db()
        self.assertEqual(order.status, PaymentOrder.OrderStatus.PENDING_SETTLE)

        va = self._usd_va()
        self.assertEqual(va.ledger_balance, Decimal("0.00"))
        self.assertEqual(va.available_balance, Decimal("0.00"))
        self.assertEqual(
            VaLedgerEntry.objects.filter(
                order=order, entry_type="DEBIT", source_type="SETTLEMENT", is_deleted=False,
            ).count(),
            1,
        )

        AccountService().debit_va_for_order_outflow(order, remark="settlement retry")
        va.refresh_from_db()
        self.assertEqual(va.ledger_balance, Decimal("0.00"))
        self.assertEqual(
            VaLedgerEntry.objects.filter(
                order=order, entry_type="DEBIT", source_type="SETTLEMENT", is_deleted=False,
            ).count(),
            1,
        )

    def test_collection_uses_from_currency_not_cny_fallback(self):
        ensure_merchant_virtual_account(self.merchant)
        cny = VirtualAccount.objects.get(merchant=self.merchant, currency="CNY", is_deleted=False)
        self.assertEqual(cny.ledger_balance, Decimal("0.00"))

        order = PaymentOrder.objects.create(
            order_no="RMT_FLOAT_USD_CNY",
            merchant_order_no="M_FLOAT_USD_CNY",
            unique_identification_no="UIN_FLOAT_USD_CNY",
            idempotency_key="IDEM_FLOAT_USD_CNY",
            merchant=self.merchant,
            amount=Decimal("10000.00"),
            currency="CNY",
            from_currency="USD",
            to_currency="CNY",
            beneficiary_name="ACME Supplier",
            fee_amount=Decimal("100.00"),
            status=PaymentOrder.OrderStatus.PENDING_PAY,
            pay_method="WIRE_TRANSFER",
            expire_at=timezone.now() + timedelta(days=7),
        )
        PaymentConfirmService().manual_confirm_by_order_no(order.order_no, bank_txn_id="BNK_USD")
        cny.refresh_from_db()
        self.assertEqual(cny.ledger_balance, Decimal("0.00"))
        usd = self._usd_va()
        self.assertIsNotNone(usd)
        self.assertEqual(usd.ledger_balance, Decimal("10000.00"))
