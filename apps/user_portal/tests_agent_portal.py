"""Agent self-service HTTP isolation tests."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.agent.models import Agent
from apps.settlement.models import FeeShare
from apps.user_portal.models import EndUser
from apps.user_portal.services import UserService
from apps.user_portal.tests import ONBOARDING_PAYLOAD


class AgentPortalApiTests(TestCase):
    def setUp(self):
        self.svc = UserService()
        self.svc.register(phone="13900000061", password="Test@123", sms_code="")
        self.user = EndUser.objects.get(phone="13900000061")
        self.svc.choose_role(self.user, "agent")
        self.user.refresh_from_db()
        self.svc.submit_onboarding(self.user, ONBOARDING_PAYLOAD)
        self.svc.review_onboarding(self.user, action="approve", reviewer="ops")
        self.user.refresh_from_db()
        self.client = APIClient()
        token = UserService._generate_token(str(self.user.id), user_type="user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_me_returns_own_agent_without_secret(self):
        res = self.client.get("/api/v1/user/agent/me/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["agent_no"], self.user.default_agent.agent_no)
        self.assertNotIn("api_secret", res.data)

    def test_earnings_exclude_other_agent_rows(self):
        other = Agent.objects.create(agent_no="AG_HTTP_LEAK", agent_name="Leak Agent")
        FeeShare.objects.create(
            agent=other,
            order_no="RMT_HTTP_LEAK",
            merchant_name="Leak Co",
            agent_name=other.agent_name,
            agent_fee=Decimal("9.00"),
            amount=Decimal("90.00"),
        )
        FeeShare.objects.create(
            agent=self.user.default_agent,
            order_no="RMT_MINE",
            merchant_name="Mine Co",
            agent_name=self.user.default_agent.agent_name,
            agent_fee=Decimal("3.00"),
            amount=Decimal("30.00"),
        )
        res = self.client.get("/api/v1/user/agent/earnings/")
        self.assertEqual(res.status_code, 200)
        nos = [row["order_no"] for row in res.data["items"]]
        self.assertEqual(nos, ["RMT_MINE"])
        self.assertEqual(res.data["period"], "month")
        self.assertEqual(len(res.data["summary"]), 1)
        self.assertEqual(res.data["summary"][0]["agent_fee_total"], "3.00")
        self.assertEqual(res.data["by_customer"][0]["merchant_name"], "Mine Co")
        self.assertEqual(res.data["by_customer"][0]["agent_fee_total"], "3.00")

    def test_earnings_summary_period_and_customer_filter(self):
        from datetime import timedelta

        from django.utils import timezone

        agent = self.user.default_agent
        FeeShare.objects.create(
            agent=agent,
            order_no="RMT_A1",
            merchant_name="Alpha Co",
            agent_name=agent.agent_name,
            agent_fee=Decimal("10.00"),
            amount=Decimal("100.00"),
        )
        FeeShare.objects.create(
            agent=agent,
            order_no="RMT_A2",
            merchant_name="Alpha Co",
            agent_name=agent.agent_name,
            agent_fee=Decimal("5.50"),
            amount=Decimal("55.00"),
        )
        FeeShare.objects.create(
            agent=agent,
            order_no="RMT_B1",
            merchant_name="Beta Co",
            agent_name=agent.agent_name,
            agent_fee=Decimal("2.00"),
            amount=Decimal("20.00"),
        )
        old = FeeShare.objects.create(
            agent=agent,
            order_no="RMT_OLD",
            merchant_name="Alpha Co",
            agent_name=agent.agent_name,
            agent_fee=Decimal("99.00"),
            amount=Decimal("990.00"),
        )
        FeeShare.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=400)
        )

        res = self.client.get("/api/v1/user/agent/earnings/", {"period": "year"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["summary"][0]["agent_fee_total"], "17.50")
        by_name = {row["merchant_name"]: row for row in res.data["by_customer"]}
        self.assertEqual(by_name["Alpha Co"]["agent_fee_total"], "15.50")
        self.assertEqual(by_name["Alpha Co"]["order_count"], 2)
        self.assertEqual(by_name["Beta Co"]["agent_fee_total"], "2.00")

        res = self.client.get(
            "/api/v1/user/agent/earnings/",
            {"period": "all", "merchant_name": "Alpha Co"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["summary"][0]["agent_fee_total"], "114.50")
        self.assertEqual(res.data["total"], 3)
        self.assertTrue(all(row["merchant_name"] == "Alpha Co" for row in res.data["items"]))
        self.assertTrue(all(row["merchant_name"] == "Alpha Co" for row in res.data["by_customer"]))

    def test_customer_cannot_read_agent_workspace(self):
        self.svc.register(phone="13900000062", password="Test@123", sms_code="")
        customer = EndUser.objects.get(phone="13900000062")
        self.svc.choose_role(customer, "customer")
        token = UserService._generate_token(str(customer.id), user_type="user")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        res = client.get("/api/v1/user/agent/me/")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], "NOT_AGENT")

    def test_choose_role_endpoint_rejects_second_choice(self):
        res = self.client.post("/api/v1/user/profile/choose-role/", {"role": "customer"}, format="json")
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.data["code"], "ROLE_ALREADY_CHOSEN")

    def test_kyc_list_and_review_own_referred_customer(self):
        from apps.user_portal.models import UserOnboarding

        self.svc.register(phone="13900000063", password="Test@123", sms_code="")
        customer = EndUser.objects.get(phone="13900000063")
        self.svc.choose_role(customer, "customer")
        customer.refresh_from_db()
        payload = {
            **ONBOARDING_PAYLOAD,
            "basic": {
                **ONBOARDING_PAYLOAD["basic"],
                "legal_name": "Referred Co",
                "contact_phone": "13900000063",
                "agent_code": self.user.default_agent.agent_no,
            },
        }
        self.svc.submit_onboarding(customer, payload)
        listed = self.client.get("/api/v1/user/agent/kyc/", {"stage": "needs_review"})
        self.assertEqual(listed.status_code, 200)
        ids = [row["id"] for row in listed.data["items"]]
        self.assertIn(str(customer.id), ids)
        detail = self.client.get(f"/api/v1/user/agent/kyc/{customer.id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["data"]["basic"]["legal_name"], "Referred Co")
        reviewed = self.client.post(
            f"/api/v1/user/agent/kyc/{customer.id}/review/",
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(reviewed.data["agent_review_status"], UserOnboarding.AgentReviewStatus.APPROVED)
        customer.refresh_from_db()
        self.assertEqual(customer.onboarding_status, "pending")
        empty = self.client.get("/api/v1/user/agent/kyc/", {"stage": "needs_review"})
        self.assertNotIn(str(customer.id), [row["id"] for row in empty.data["items"]])

    def test_kyc_cannot_review_other_agent_customer(self):
        other = Agent.objects.create(agent_no="Aa11Bb22", agent_name="Other HTTP Agent")
        self.svc.register(phone="13900000064", password="Test@123", sms_code="")
        customer = EndUser.objects.get(phone="13900000064")
        self.svc.choose_role(customer, "customer")
        customer.refresh_from_db()
        payload = {
            **ONBOARDING_PAYLOAD,
            "basic": {
                **ONBOARDING_PAYLOAD["basic"],
                "contact_phone": "13900000064",
                "agent_code": other.agent_no,
            },
        }
        self.svc.submit_onboarding(customer, payload)
        res = self.client.post(
            f"/api/v1/user/agent/kyc/{customer.id}/review/",
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], "AGENT_KYC_FORBIDDEN")

    def test_virtual_accounts_only_own_customers(self):
        from apps.account.models import VirtualAccount
        from apps.agent.services import ensure_agent_accounts
        from apps.merchant.models import Merchant
        from apps.merchant.services import (
            ensure_merchant_multi_currency_accounts,
            ensure_merchant_virtual_account,
        )

        mine = Merchant.objects.create(
            merchant_no="VA_AG_MINE",
            merchant_name="Mine Customer",
            api_key="ak_va_ag_mine",
            api_secret="sk_va_ag_mine",
            status=Merchant.Status.ACTIVE,
            agent=self.user.default_agent,
        )
        ensure_merchant_multi_currency_accounts(mine)

        other_agent = Agent.objects.create(agent_no="AG_VA_OTH", agent_name="Other VA Agent")
        other = Merchant.objects.create(
            merchant_no="VA_AG_OTH",
            merchant_name="Other Customer",
            api_key="ak_va_ag_oth",
            api_secret="sk_va_ag_oth",
            status=Merchant.Status.ACTIVE,
            agent=other_agent,
        )
        ensure_merchant_virtual_account(other)
        ensure_agent_accounts(self.user.default_agent)

        listed = self.client.get("/api/v1/user/agent/virtual-accounts/")
        self.assertEqual(listed.status_code, 200)
        rows = listed.data["results"]
        self.assertEqual([row["merchant_no"] for row in rows], ["VA_AG_MINE"])
        self.assertEqual(rows[0]["va_count"], 4)
        self.assertEqual(len(rows[0]["accounts"]), 4)
        self.assertIn("totals", rows[0])
        self.assertEqual(len(rows[0]["totals"]), 4)
        for total in rows[0]["totals"]:
            self.assertIn("currency", total)
            self.assertIn("available_balance", total)
            self.assertIn("ledger_balance", total)
            self.assertEqual(total["available_balance"], "0.00")

        merchants = self.client.get("/api/v1/user/agent/merchants/")
        self.assertEqual(merchants.status_code, 200)
        mine_row = next(row for row in merchants.data["items"] if row["merchant_no"] == "VA_AG_MINE")
        self.assertIn("balances", mine_row)

        stats = self.client.get("/api/v1/user/agent/virtual-accounts/stats/")
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.data["total"], 4)

        own_va = mine.virtual_accounts.filter(is_deleted=False).first()
        tx = self.client.get(f"/api/v1/user/agent/virtual-accounts/{own_va.id}/transactions/")
        self.assertEqual(tx.status_code, 200)

        other_va = other.virtual_accounts.filter(is_deleted=False).first()
        forbidden = self.client.get(f"/api/v1/user/agent/virtual-accounts/{other_va.id}/transactions/")
        self.assertEqual(forbidden.status_code, 404)
        self.assertEqual(forbidden.data["code"], "VA_NOT_FOUND")

        agent_vla = VirtualAccount.objects.filter(
            agent=self.user.default_agent, merchant__isnull=True, is_deleted=False,
        ).first()
        self.assertIsNotNone(agent_vla)
        leak = self.client.get(f"/api/v1/user/agent/virtual-accounts/{agent_vla.id}/transactions/")
        self.assertEqual(leak.status_code, 404)

    def test_fund_transfers_disabled_for_agent_portal(self):
        from apps.agent.services import ensure_agent_accounts

        ensure_agent_accounts(self.user.default_agent)
        accounts = self.client.get("/api/v1/user/agent/fund-transfers/accounts/")
        self.assertEqual(accounts.status_code, 200)
        self.assertEqual(accounts.data["items"], [])

        listed = self.client.get("/api/v1/user/agent/fund-transfers/")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.data["items"], [])

        created = self.client.post(
            "/api/v1/user/agent/fund-transfers/",
            {
                "from_account": "x",
                "to_account": "y",
                "amount": "12.50",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 400)
        self.assertEqual(created.data["code"], "AGENT_HAS_NO_ACCOUNT")

        executed = self.client.post("/api/v1/user/agent/fund-transfers/T_ANY/execute/")
        self.assertEqual(executed.status_code, 400)
        self.assertEqual(executed.data["code"], "AGENT_HAS_NO_ACCOUNT")


class AgentProxyRemittanceApiTests(TestCase):
    def setUp(self):
        from apps.exchange.models import ExchangeRate
        from apps.payment.tests_remittance_v2 import create_eligible_merchant
        from django.utils import timezone

        self.svc = UserService()
        self.svc.register(phone="13900000071", password="Test@123", sms_code="")
        self.agent_user = EndUser.objects.get(phone="13900000071")
        self.svc.choose_role(self.agent_user, "agent")
        self.agent_user.refresh_from_db()
        self.svc.submit_onboarding(self.agent_user, {
            **ONBOARDING_PAYLOAD,
            "basic": {**ONBOARDING_PAYLOAD["basic"], "contact_phone": "13900000071"},
        })
        self.svc.review_onboarding(self.agent_user, action="approve", reviewer="ops")
        self.agent_user.refresh_from_db()

        self.merchant = create_eligible_merchant("AGPROXY")
        self.merchant.agent = self.agent_user.default_agent
        self.merchant.save(update_fields=["agent", "updated_at"])

        self.svc.register(phone="13900000072", password="Test@123", sms_code="")
        self.customer = EndUser.objects.get(phone="13900000072")
        self.svc.choose_role(self.customer, "customer")
        self.customer.refresh_from_db()
        self.customer.default_merchant = self.merchant
        self.customer.onboarding_status = "approved"
        self.customer.save(update_fields=["default_merchant", "onboarding_status", "updated_at"])

        ExchangeRate.objects.create(
            date=timezone.localdate(),
            from_currency="USD",
            to_currency="CNY",
            rate=Decimal("7"),
            source="TEST",
        )

        self.client = APIClient()
        token = UserService._generate_token(str(self.agent_user.id), user_type="user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_merchants_include_eligibility_and_end_user(self):
        res = self.client.get("/api/v1/user/agent/merchants/")
        self.assertEqual(res.status_code, 200)
        row = next(item for item in res.data["items"] if item["id"] == str(self.merchant.id))
        self.assertTrue(row["remittance_eligibility"]["eligible"])
        self.assertEqual(row["end_user_id"], str(self.customer.id))

    def test_agent_quote_and_apply_skips_agent_review(self):
        from apps.payment.models import PaymentOrder

        quote = self.client.post(
            "/api/v1/user/agent/payments/quote/",
            {
                "merchant_id": str(self.merchant.id),
                "amount": "1000.00",
                "from_currency": "USD",
                "to_currency": "CNY",
                "fee_bearing": "OUR",
            },
            format="json",
        )
        self.assertEqual(quote.status_code, 201)
        quote_id = quote.data["quote_id"]

        apply = self.client.post(
            "/api/v1/user/agent/payments/apply/",
            {
                "merchant_id": str(self.merchant.id),
                "quote_id": quote_id,
                "beneficiary_name": "Supplier Co",
                "beneficiary_bank": "Bank",
                "beneficiary_account": "998877",
                "beneficiary_swift": "TESTUS33",
                "beneficiary_address": "1 Road",
                "remittance_purpose": "Goods",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="idem-ag-proxy-ok",
        )
        self.assertEqual(apply.status_code, 201)
        self.assertEqual(apply.data["status"], PaymentOrder.OrderStatus.PENDING_REVIEW)
        self.assertEqual(apply.data["agent_review_status"], PaymentOrder.AgentReviewStatus.NONE)
        order = PaymentOrder.objects.get(order_no=apply.data["order_no"])
        self.assertEqual(order.user_id, str(self.customer.id))

        customer_client = APIClient()
        customer_token = UserService._generate_token(str(self.customer.id), user_type="user")
        customer_client.credentials(HTTP_AUTHORIZATION=f"Bearer {customer_token}")
        listed = customer_client.get("/api/v1/user/payments/remittances/")
        self.assertEqual(listed.status_code, 200)
        order_nos = [row["order_no"] for row in listed.data["results"]]
        self.assertIn(apply.data["order_no"], order_nos)

    def test_agent_cannot_quote_unbound_merchant(self):
        from apps.payment.tests_remittance_v2 import create_eligible_merchant

        other = create_eligible_merchant("AGOTH")
        res = self.client.post(
            "/api/v1/user/agent/payments/quote/",
            {
                "merchant_id": str(other.id),
                "amount": "100.00",
                "from_currency": "USD",
                "to_currency": "CNY",
                "fee_bearing": "OUR",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], "AGENT_MERCHANT_FORBIDDEN")

    def test_customer_cannot_call_agent_quote(self):
        customer_client = APIClient()
        token = UserService._generate_token(str(self.customer.id), user_type="user")
        customer_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        res = customer_client.post(
            "/api/v1/user/agent/payments/quote/",
            {
                "merchant_id": str(self.merchant.id),
                "amount": "100.00",
                "from_currency": "USD",
                "to_currency": "CNY",
                "fee_bearing": "OUR",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], "NOT_AGENT")

    def test_agent_cannot_apply_customer_quote(self):
        from apps.payment.services.remittance_quote import RemittanceQuoteService

        quote = RemittanceQuoteService().create_quote(
            merchant=self.merchant,
            amount=Decimal("500"),
            from_currency="USD",
            to_currency="CNY",
            fee_bearing="OUR",
            actor_type="CUSTOMER",
            user_id=str(self.customer.id),
        )
        res = self.client.post(
            "/api/v1/user/agent/payments/apply/",
            {
                "merchant_id": str(self.merchant.id),
                "quote_id": quote.quote_no,
                "beneficiary_name": "Supplier Co",
                "beneficiary_bank": "Bank",
                "beneficiary_account": "998877",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="idem-ag-steal-quote",
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], "QUOTE_OWNER_MISMATCH")

    def test_ineligible_merchant_quote_returns_422(self):
        from apps.merchant.models import Merchant

        self.merchant.status = Merchant.Status.SUSPENDED
        self.merchant.save(update_fields=["status", "updated_at"])
        res = self.client.post(
            "/api/v1/user/agent/payments/quote/",
            {
                "merchant_id": str(self.merchant.id),
                "amount": "100.00",
                "from_currency": "USD",
                "to_currency": "CNY",
                "fee_bearing": "OUR",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.data["code"], "MERCHANT_SUSPENDED")


class AgentCurrencyPoolApiTests(TestCase):
    def setUp(self):
        self.svc = UserService()
        self.svc.register(phone="13900000071", password="Test@123", sms_code="")
        self.user = EndUser.objects.get(phone="13900000071")
        self.svc.choose_role(self.user, "agent")
        self.user.refresh_from_db()
        self.svc.submit_onboarding(self.user, ONBOARDING_PAYLOAD)
        self.svc.review_onboarding(self.user, action="approve", reviewer="ops")
        self.user.refresh_from_db()
        self.client = APIClient()
        token = UserService._generate_token(str(self.user.id), user_type="user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_accounts_sum_customer_balances_not_agent_pool(self):
        from apps.account.models import NostroAccount
        from apps.account.services import AccountService
        from apps.agent.services import ensure_agent_accounts, get_agent_ledger_va
        from apps.merchant.models import Merchant
        from apps.merchant.services import ensure_merchant_currency_account

        ensure_agent_accounts(self.user.default_agent, "CNY")
        merchant = Merchant.objects.create(
            merchant_no="MC_SUM_01",
            merchant_name="Sum Customer",
            api_key="ak_sum_01",
            api_secret="sk_sum_01",
            status=Merchant.Status.ACTIVE,
            agent=self.user.default_agent,
        )
        ensure_merchant_currency_account(merchant, "CNY")
        deposit = AccountService().create_customer_deposit(
            merchant=merchant, currency="CNY", amount="45.00",
        )
        AccountService().approve_deposit(deposit, reviewer="ops")

        listed = self.client.get("/api/v1/user/agent/accounts/")
        self.assertEqual(listed.status_code, 200, listed.content)
        cny = next(row for row in listed.data["items"] if row["currency"] == "CNY")
        self.assertEqual(cny["balance"], "45.00")

        agent_va = get_agent_ledger_va(
            self.user.default_agent, NostroAccount.AccountType.CURRENT, "CNY",
        )
        self.assertEqual(agent_va.available_balance, Decimal("0.00"))

        me = self.client.get("/api/v1/user/agent/me/")
        self.assertEqual(me.status_code, 200)
        me_cny = next(row for row in me.data["accounts"] if row["currency"] == "CNY")
        self.assertEqual(me_cny["balance"], "45.00")
        self.assertNotIn("account_type", me_cny)

        merchants = self.client.get("/api/v1/user/agent/merchants/")
        row = next(r for r in merchants.data["items"] if r["merchant_no"] == "MC_SUM_01")
        self.assertEqual(row["balances"], [{"currency": "CNY", "available_balance": "45.00"}])

    def test_enable_and_self_top_up_are_rejected(self):
        enable = self.client.post(
            "/api/v1/user/agent/accounts/enable/",
            {"currency": "USD"},
            format="json",
        )
        self.assertEqual(enable.status_code, 400)
        self.assertEqual(enable.data["code"], "AGENT_HAS_NO_ACCOUNT")

        created = self.client.post(
            "/api/v1/user/agent/accounts/deposits/",
            {"currency": "CNY", "amount": "30.00", "remark": "agent float"},
            format="json",
        )
        self.assertEqual(created.status_code, 400)
        self.assertEqual(created.data["code"], "AGENT_HAS_NO_ACCOUNT")

        listed = self.client.get("/api/v1/user/agent/accounts/deposits/")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.data["total"], 0)
        self.assertEqual(listed.data["items"], [])

