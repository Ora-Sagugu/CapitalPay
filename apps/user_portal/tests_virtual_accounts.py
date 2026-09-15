"""Customer virtual-account opt-in APIs."""
from rest_framework.test import APIClient

from django.test import TestCase

from apps.account.models import VirtualAccount
from apps.core.currencies import ISO_4217_CODES, is_supported_currency
from apps.user_portal.models import EndUser
from apps.user_portal.services import UserService


class CustomerVirtualAccountApiTests(TestCase):
    def setUp(self):
        self.svc = UserService()
        self.svc.register(phone="13900000080", password="Test@123", sms_code="")
        self.user = EndUser.objects.get(phone="13900000080")
        self.svc.choose_role(self.user, "customer")
        self.user.refresh_from_db()
        self.svc.submit_onboarding(self.user, {
            "basic": {
                "legal_name": "VA Opt In Ltd",
                "id_type": "id_card",
                "id_number": "VA-ID-001",
                "contact_phone": "13900000080",
            },
            "finance": {
                "bank_name": "Equity Bank",
                "account_name": "VA Opt In Ltd",
                "bank_account": "88990011",
            },
            "images": {
                "license_image": "kyc/license.png",
                "id_front_image": "kyc/front.png",
                "id_back_image": "kyc/back.png",
            },
        })
        self.svc.review_onboarding(self.user, action="approve", reviewer="ops")
        self.user.refresh_from_db()
        self.client = APIClient()
        token = UserService._generate_token(str(self.user.id), user_type="user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_catalog_includes_iso_currencies(self):
        res = self.client.get("/api/v1/user/accounts/currencies/")
        self.assertEqual(res.status_code, 200)
        codes = {item["code"] for item in res.data["items"]}
        self.assertTrue({"JPY", "GBP", "USD", "CNY"}.issubset(codes))
        self.assertEqual(len(codes), len(ISO_4217_CODES))
        self.assertTrue(is_supported_currency("jpy"))

    def test_virtual_list_empty_until_currency_enabled(self):
        res = self.client.get("/api/v1/user/accounts/virtual/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["virtual_accounts"], [])
        self.assertFalse(
            VirtualAccount.objects.filter(merchant=self.user.default_merchant, is_deleted=False).exists()
        )

    def test_enable_jpy_creates_nostro_and_va(self):
        res = self.client.post("/api/v1/user/accounts/virtual/enable/", {"currency": "JPY"}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        rows = res.data["virtual_accounts"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["currency"], "JPY")
        self.assertEqual(rows[0]["balance"], "0.00")
        merchant = self.user.default_merchant
        self.assertEqual(
            merchant.virtual_accounts.filter(is_deleted=False, currency="JPY").count(),
            1,
        )
        self.assertTrue(
            merchant.nostro_accounts.filter(is_deleted=False, currency="JPY").exists()
        )

    def test_enable_is_idempotent_and_accumulates(self):
        first = self.client.post("/api/v1/user/accounts/virtual/enable/", {"currency": "gbp"}, format="json")
        again = self.client.post("/api/v1/user/accounts/virtual/enable/", {"currency": "GBP"}, format="json")
        usd = self.client.post("/api/v1/user/accounts/virtual/enable/", {"currency": "USD"}, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(usd.status_code, 200)
        merchant = self.user.default_merchant
        self.assertEqual(
            merchant.virtual_accounts.filter(is_deleted=False, currency="GBP").count(),
            1,
        )
        codes = {row["currency"] for row in usd.data["virtual_accounts"]}
        self.assertEqual(codes, {"GBP", "USD"})

    def test_enable_rejects_invalid_currency(self):
        res = self.client.post("/api/v1/user/accounts/virtual/enable/", {"currency": "XXX"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["code"], "INVALID_CURRENCY")
        self.assertFalse(
            VirtualAccount.objects.filter(merchant=self.user.default_merchant, is_deleted=False).exists()
        )

    def test_top_up_creates_pending_deposit_and_credits_after_review(self):
        from apps.account.models import DepositRequest
        from apps.account.services import AccountService

        enabled = self.client.post("/api/v1/user/accounts/virtual/enable/", {"currency": "JPY"}, format="json")
        self.assertEqual(enabled.status_code, 200)
        res = self.client.post(
            "/api/v1/user/accounts/virtual/top-up/",
            {"currency": "JPY", "amount": "40.00", "remark": "customer float"},
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data["status"], "PENDING")
        self.assertEqual(res.data["source"], "CUSTOMER")
        listed = self.client.get("/api/v1/user/accounts/virtual/")
        self.assertEqual(listed.data["virtual_accounts"][0]["balance"], "0.00")
        deposit = DepositRequest.objects.get(deposit_no=res.data["deposit_no"])
        AccountService().approve_deposit(deposit, reviewer="ops")
        listed = self.client.get("/api/v1/user/accounts/virtual/")
        self.assertEqual(listed.data["virtual_accounts"][0]["balance"], "40.00")

    def test_bind_card_opens_currency_va_and_lists_bank_details(self):
        res = self.client.post(
            "/api/v1/user/accounts/bind/",
            {
                "bank_code": "EQTY",
                "bank_name": "Equity Bank",
                "account_holder": "VA Opt In Ltd",
                "account_number": "88990011",
                "currency": "USD",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data["currency"], "USD")
        self.assertEqual(res.data["bound"]["bank_code"], "EQTY")
        self.assertEqual(res.data["bound"]["account_number"], "****0011")
        added = res.data["added_cards"]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["bank_code"], "EQTY")
        self.assertEqual(added[0]["bank_name"], "Equity Bank")
        self.assertEqual(added[0]["balance"], "0.00")
        self.assertEqual(added[0]["currency"], "USD")
        registration = res.data["registration"]
        self.assertIsNotNone(registration)
        self.assertEqual(registration["source"], "registration")
        self.assertEqual(registration["bank_name"], "Equity Bank")

        listed = self.client.get("/api/v1/user/accounts/list/")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.data["registration"]["bank_name"], "Equity Bank")
        self.assertEqual(listed.data["registration"]["account_number"], "****0011")
        self.assertEqual(len(listed.data["added_cards"]), 1)
        self.assertEqual(listed.data["added_cards"][0]["bank_code"], "EQTY")
        self.assertEqual(listed.data["added_cards"][0]["account_number"], "****0011")
        self.assertEqual(listed.data["balances"][0]["currency"], "USD")
        self.assertEqual(listed.data["balances"][0]["balance"], "0.00")

    def test_virtual_ledger_lists_deposit_credit(self):
        from apps.account.models import DepositRequest
        from apps.account.services import AccountService

        self.client.post("/api/v1/user/accounts/virtual/enable/", {"currency": "JPY"}, format="json")
        top_up = self.client.post(
            "/api/v1/user/accounts/virtual/top-up/",
            {"currency": "JPY", "amount": "40.00", "remark": "customer float"},
            format="json",
        )
        deposit = DepositRequest.objects.get(deposit_no=top_up.data["deposit_no"])
        AccountService().approve_deposit(deposit, reviewer="ops")
        res = self.client.get("/api/v1/user/accounts/virtual/ledger/")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data["total"], 1)
        row = res.data["items"][0]
        self.assertEqual(row["currency"], "JPY")
        self.assertEqual(row["entry_type"], "CREDIT")
        self.assertEqual(row["amount"], "40.00")
        self.assertEqual(row["balance_after"], "40.00")

