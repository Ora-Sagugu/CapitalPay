"""Virtual account admin APIs."""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.account.models import VirtualAccount
from apps.agent.models import Agent
from apps.agent.services import ensure_agent_accounts
from apps.merchant.models import Merchant
from apps.merchant.services import (
    ensure_merchant_multi_currency_accounts,
    ensure_merchant_virtual_account,
)
from apps.rbac.models import SystemUser
from apps.rbac.testing import attach_super_admin


class VirtualAccountByCustomerTests(TestCase):
    def setUp(self):
        self.multi = Merchant.objects.create(
            merchant_no="VA_C001",
            merchant_name="Multi Currency Customer",
            api_key="ak_va_c001",
            api_secret="sk_va_c001",
            status=Merchant.Status.ACTIVE,
        )
        self.single = Merchant.objects.create(
            merchant_no="VA_C002",
            merchant_name="Single Currency Customer",
            api_key="ak_va_c002",
            api_secret="sk_va_c002",
            status=Merchant.Status.ACTIVE,
        )
        ensure_merchant_multi_currency_accounts(self.multi)
        ensure_merchant_virtual_account(self.single)
        self.agent = Agent.objects.create(agent_no="AG_VA_001", agent_name="VA Agent")
        ensure_agent_accounts(self.agent)

        self.client = APIClient()
        operator = SystemUser.objects.create(
            username="va-ops",
            password_hash="test",
            real_name="VA Operator",
        )
        attach_super_admin(operator)
        self.client.force_authenticate(operator)

    def test_groups_one_row_per_customer(self):
        resp = self.client.get("/api/v1/admin/virtual-accounts/by-customer/")
        self.assertEqual(resp.status_code, 200, resp.content)
        payload = resp.json()
        self.assertEqual(payload["count"], 2)
        by_no = {row["merchant_no"]: row for row in payload["results"]}
        self.assertEqual(set(by_no), {"VA_C001", "VA_C002"})

        multi_row = by_no["VA_C001"]
        self.assertEqual(multi_row["va_count"], 4)
        self.assertEqual(multi_row["currencies"], ["CNY", "USD", "EUR", "HKD"])
        self.assertEqual(len(multi_row["accounts"]), 4)
        self.assertEqual({item["currency"] for item in multi_row["accounts"]}, {"CNY", "USD", "EUR", "HKD"})
        self.assertEqual(multi_row["status"], VirtualAccount.VaStatus.ACTIVE)

        single_row = by_no["VA_C002"]
        self.assertEqual(single_row["va_count"], 1)
        self.assertEqual(len(single_row["accounts"]), 1)

    def test_search_by_va_number_returns_full_customer_accounts(self):
        va = self.multi.virtual_accounts.filter(is_deleted=False, currency="USD").first()
        resp = self.client.get("/api/v1/admin/virtual-accounts/by-customer/", {"search": va.va_number})
        self.assertEqual(resp.status_code, 200, resp.content)
        rows = resp.json()["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["merchant_no"], "VA_C001")
        self.assertEqual(rows[0]["va_count"], 4)

    def test_status_filter_keeps_all_customer_accounts(self):
        va = self.single.virtual_accounts.filter(is_deleted=False).first()
        va.status = VirtualAccount.VaStatus.REVOKED
        va.save(update_fields=["status"])
        resp = self.client.get("/api/v1/admin/virtual-accounts/by-customer/", {"status": "REVOKED"})
        self.assertEqual(resp.status_code, 200, resp.content)
        rows = resp.json()["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["merchant_no"], "VA_C002")
        self.assertEqual(rows[0]["status"], VirtualAccount.VaStatus.REVOKED)
        self.assertEqual(len(rows[0]["accounts"]), 1)
