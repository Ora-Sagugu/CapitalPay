"""Deposit approval credits customer VA only (agent has no operable book)."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.account.models import DepositRequest, NostroAccount, VaLedgerEntry
from apps.account.services import AccountService
from apps.agent.models import Agent
from apps.agent.services import ensure_agent_accounts, get_agent_ledger_va
from apps.merchant.models import Merchant
from apps.merchant.services import ensure_merchant_currency_account
from apps.rbac.models import SystemUser
from apps.rbac.testing import attach_super_admin


class DepositCurrencyPoolTests(TestCase):
    def setUp(self):
        self.svc = AccountService()
        self.agent = Agent.objects.create(agent_no="AG_POOL_01", agent_name="Pool Agent")
        ensure_agent_accounts(self.agent, "CNY")
        self.merchant = Merchant.objects.create(
            merchant_no="MC_POOL_01",
            merchant_name="Pool Customer",
            api_key="ak_pool_01",
            api_secret="sk_pool_01",
            status=Merchant.Status.ACTIVE,
            agent=self.agent,
        )
        self.independent = Merchant.objects.create(
            merchant_no="MC_POOL_02",
            merchant_name="Independent Customer",
            api_key="ak_pool_02",
            api_secret="sk_pool_02",
            status=Merchant.Status.ACTIVE,
        )
        self.ops = APIClient()
        operator = SystemUser.objects.create(
            username="deposit-ops",
            password_hash="test",
            real_name="Deposit Operator",
        )
        attach_super_admin(operator)
        self.ops.force_authenticate(operator)

    def _agent_current_balance(self, currency="CNY"):
        va = get_agent_ledger_va(self.agent, NostroAccount.AccountType.CURRENT, currency)
        return va.available_balance if va else Decimal("0")

    def _merchant_va_balance(self, merchant, currency="CNY"):
        va = merchant.virtual_accounts.filter(
            is_deleted=False, currency=currency,
        ).first()
        return va.available_balance if va else Decimal("0")

    def test_agent_self_deposit_does_not_credit_until_approved(self):
        deposit = self.svc.create_agent_self_deposit(
            agent=self.agent, currency="CNY", amount="100.00", remark="self",
        )
        self.assertEqual(deposit.status, DepositRequest.DepositStatus.PENDING)
        self.assertEqual(deposit.source, DepositRequest.DepositSource.AGENT_SELF)
        self.assertIsNone(deposit.merchant_id)
        self.assertEqual(self._agent_current_balance(), Decimal("0.00"))
        self.svc.approve_deposit(deposit, reviewer="ops")
        self.assertEqual(self._agent_current_balance(), Decimal("100.00"))

    def test_customer_deposit_with_agent_credits_customer_only(self):
        deposit = self.svc.create_customer_deposit(
            merchant=self.merchant, currency="CNY", amount="80.00",
        )
        self.assertEqual(deposit.agent_id, self.agent.id)
        self.assertEqual(self._merchant_va_balance(self.merchant), Decimal("0.00"))
        self.assertEqual(self._agent_current_balance(), Decimal("0.00"))
        self.svc.approve_deposit(deposit, reviewer="ops")
        self.assertEqual(self._merchant_va_balance(self.merchant), Decimal("80.00"))
        self.assertEqual(self._agent_current_balance(), Decimal("0.00"))

    def test_customer_deposit_without_agent_only_credits_customer(self):
        deposit = self.svc.create_customer_deposit(
            merchant=self.independent, currency="USD", amount="50.00",
        )
        self.assertIsNone(deposit.agent_id)
        self.svc.approve_deposit(deposit, reviewer="ops")
        self.assertEqual(self._merchant_va_balance(self.independent, "USD"), Decimal("50.00"))
        self.assertEqual(self._agent_current_balance("USD"), Decimal("0.00"))

    def test_reject_does_not_change_balances(self):
        deposit = self.svc.create_agent_self_deposit(
            agent=self.agent, currency="CNY", amount="25.00",
        )
        self.svc.reject_deposit(deposit, reviewer="ops", reason="Name mismatch")
        deposit.refresh_from_db()
        self.assertEqual(deposit.status, DepositRequest.DepositStatus.REJECTED)
        self.assertEqual(self._agent_current_balance(), Decimal("0.00"))

    def test_repeat_review_is_rejected(self):
        deposit = self.svc.create_agent_self_deposit(
            agent=self.agent, currency="CNY", amount="10.00",
        )
        self.svc.approve_deposit(deposit, reviewer="ops")
        with self.assertRaises(Exception) as ctx:
            self.svc.approve_deposit(deposit, reviewer="ops")
        self.assertEqual(ctx.exception.code, "DEPOSIT_STATUS_INVALID")

    def test_customer_outflow_does_not_debit_agent_pool(self):
        deposit = self.svc.create_customer_deposit(
            merchant=self.merchant, currency="CNY", amount="100.00",
        )
        self.svc.approve_deposit(deposit, reviewer="ops")
        va = self.merchant.virtual_accounts.filter(is_deleted=False, currency="CNY").first()
        self.svc.post_va_entry(
            virtual_account=va,
            amount=Decimal("40.00"),
            entry_type=VaLedgerEntry.EntryType.DEBIT,
            remark="Settlement",
            source_type="SETTLEMENT",
            source_id="order-1",
        )
        result = self.svc.debit_agent_pool_for_outflow(
            merchant=self.merchant,
            amount=Decimal("40.00"),
            currency="CNY",
            origin_source="SETTLEMENT",
            origin_id="order-1",
            remark="Settlement",
        )
        self.assertIsNone(result)
        self.assertEqual(self._merchant_va_balance(self.merchant), Decimal("60.00"))
        self.assertEqual(self._agent_current_balance(), Decimal("0.00"))

    def test_ops_review_api_approves_agent_self_deposit(self):
        deposit = self.svc.create_agent_self_deposit(
            agent=self.agent, currency="CNY", amount="12.50",
        )
        res = self.ops.post(
            f"/api/v1/admin/deposits/{deposit.deposit_no}/review/",
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data["status"], "APPROVED")
        self.assertEqual(self._agent_current_balance(), Decimal("12.50"))

    def test_ops_list_includes_source_and_nullable_parties(self):
        self.svc.create_agent_self_deposit(agent=self.agent, currency="CNY", amount="1.00")
        self.svc.create_customer_deposit(merchant=self.independent, currency="USD", amount="2.00")
        res = self.ops.get("/api/v1/admin/deposits/")
        self.assertEqual(res.status_code, 200, res.content)
        rows = res.data["results"] if isinstance(res.data, dict) and "results" in res.data else res.data
        sources = {row["source"] for row in rows}
        self.assertIn("AGENT_SELF", sources)
        self.assertIn("CUSTOMER", sources)
        agent_row = next(row for row in rows if row["source"] == "AGENT_SELF")
        self.assertEqual(agent_row["agent_name"], "Pool Agent")
        self.assertEqual(agent_row["merchant_name"], "")
        customer_row = next(row for row in rows if row["source"] == "CUSTOMER")
        self.assertEqual(customer_row["merchant_name"], "Independent Customer")
        self.assertEqual(customer_row["agent_name"], "")

    def test_enable_currency_is_idempotent(self):
        first = ensure_agent_accounts(self.agent, "USD")
        again = ensure_agent_accounts(self.agent, "USD")
        self.assertTrue(first)
        self.assertEqual(again, [])
        self.assertEqual(
            self.agent.nostro_accounts.filter(
                is_deleted=False,
                account_type=NostroAccount.AccountType.CURRENT,
                currency="USD",
            ).count(),
            1,
        )
        ensure_merchant_currency_account(self.merchant, "USD")
        deposit = self.svc.create_customer_deposit(
            merchant=self.merchant, currency="USD", amount="5.00",
        )
        self.svc.approve_deposit(deposit, reviewer="ops")
        self.assertEqual(self._merchant_va_balance(self.merchant, "USD"), Decimal("5.00"))
        self.assertEqual(self._agent_current_balance("USD"), Decimal("0.00"))
