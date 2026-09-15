from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection, connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.core.exceptions import BusinessException
from apps.exchange.models import ExchangeRate
from apps.merchant.models import (
    Merchant,
    MerchantFee,
    MerchantKYC,
    MerchantPaymentProduct,
    MerchantSettlementAccount,
)
from apps.merchant.services import MerchantLifecycleService
from apps.param.models import RemittanceFeeConfig
from apps.payment.models import (
    MerchantDailyRemittanceUsage,
    PaymentOrder,
    RemittanceQuote,
)
from apps.payment.services.remittance_application import RemittanceApplicationService
from apps.payment.services.remittance_policy import RemittanceEligibilityPolicy
from apps.payment.services.remittance_quote import RemittanceQuoteService
from apps.settlement.models import FeeShare


def ensure_global_remittance_fee(
    *,
    fixed_fee=Decimal("2.00"),
    percent_rate=Decimal("0.30"),
    max_fee=Decimal("100.00"),
):
    config = RemittanceFeeConfig.get_config()
    config.fixed_fee = fixed_fee
    config.percent_rate = percent_rate
    config.max_fee = max_fee
    config.updated_by = "tests"
    config.save()
    return config


def create_eligible_merchant(
    suffix="01",
    *,
    max_single=Decimal("5000"),
    daily_limit=Decimal("10000"),
    with_merchant_fee=False,
):
    ensure_global_remittance_fee()
    merchant = Merchant.objects.create(
        merchant_no=f"MV2{suffix}",
        merchant_name=f"Remittance Merchant {suffix}",
        license_expiry_date=timezone.localdate() + timedelta(days=365),
        risk_level="LOW",
        sanction_status="UN",
        max_single_amount=max_single,
        daily_limit=daily_limit,
        daily_count=10,
    )
    MerchantKYC.objects.create(
        merchant=merchant,
        legal_person="Test Owner",
        id_number="encrypted",
        business_license="encrypted",
        kyc_status=MerchantKYC.Status.APPROVED,
    )
    MerchantSettlementAccount.objects.create(
        merchant=merchant,
        bank_name="Test Bank",
        account_name=merchant.merchant_name,
        account_number="encrypted",
        is_default=True,
    )
    MerchantPaymentProduct.objects.create(
        merchant=merchant,
        product_type=MerchantFee.ProductType.WIRE_TRANSFER,
        is_enabled=True,
        max_single_amount=max_single,
        daily_limit=daily_limit,
    )
    if with_merchant_fee:
        MerchantFee.objects.create(
            merchant=merchant,
            product_type=MerchantFee.ProductType.WIRE_TRANSFER,
            fee_model=MerchantFee.FeeModel.PERCENTAGE,
            fee_rate=Decimal("0.999"),
            fixed_fee=Decimal("99"),
            min_fee=Decimal("1"),
            max_fee=Decimal("1"),
            effective_from=timezone.localdate(),
        )
    return MerchantLifecycleService().activate(
        merchant,
        reason_code="TEST_APPROVED",
        comment="test fixture",
        actor="tests",
        source="TEST",
    )


def submit_payload(quote):
    return {
        "quote_id": quote.quote_no,
        "beneficiary_name": "ACME Supplier",
        "beneficiary_bank": "Supplier Bank",
        "beneficiary_account": "00112233",
        "beneficiary_swift": "TESTUS33",
        "beneficiary_address": "1 Main Street",
        "remittance_purpose": "Invoice payment",
        "contract_file": "",
    }


class RemittanceEligibilityAndQuoteTests(TestCase):
    def setUp(self):
        self.merchant = create_eligible_merchant()
        ExchangeRate.objects.create(
            date=timezone.localdate(),
            from_currency="USD",
            to_currency="CNY",
            rate=Decimal("7"),
            source="TEST",
        )

    def quote(self, fee_bearing):
        return RemittanceQuoteService().create_quote(
            merchant=self.merchant,
            amount=Decimal("1000"),
            from_currency="USD",
            to_currency="CNY",
            fee_bearing=fee_bearing,
            actor_type="ADMIN",
        )

    def test_our_and_ben_amounts_are_distinct_and_decimal_exact(self):
        our = self.quote("OUR")
        ben = self.quote("BEN")
        self.assertEqual(our.fee_amount, Decimal("5.00"))
        self.assertEqual(our.sender_total_amount, Decimal("1005.00"))
        self.assertEqual(our.settle_amount, Decimal("7000.00"))
        self.assertEqual(ben.sender_total_amount, Decimal("1000.00"))
        self.assertEqual(ben.settle_amount, Decimal("6965.00"))

    def test_sha_fee_bearing_splits_charges_evenly(self):
        sha = self.quote("SHA")
        self.assertEqual(sha.fee_amount, Decimal("5.00"))
        self.assertEqual(sha.sender_fee_amount, Decimal("2.50"))
        self.assertEqual(sha.beneficiary_fee_amount, Decimal("2.50"))
        self.assertEqual(sha.sender_total_amount, Decimal("1002.50"))
        self.assertEqual(sha.settle_amount, Decimal("6982.50"))

    def test_sha_odd_cent_goes_to_remitter(self):
        ensure_global_remittance_fee(
            fixed_fee=Decimal("5.01"),
            percent_rate=Decimal("0"),
            max_fee=Decimal("100.00"),
        )
        sha = self.quote("SHA")
        self.assertEqual(sha.fee_amount, Decimal("5.01"))
        self.assertEqual(sha.sender_fee_amount, Decimal("2.51"))
        self.assertEqual(sha.beneficiary_fee_amount, Decimal("2.50"))
        self.assertEqual(sha.sender_total_amount, Decimal("1002.51"))
        self.assertEqual(sha.settle_amount, Decimal("6982.50"))

    def test_unknown_fee_bearing_is_rejected(self):
        with self.assertRaises(BusinessException) as caught:
            self.quote("XYZ")
        self.assertEqual(caught.exception.code, "FEE_BEARING_INVALID")

    def test_same_currency_uses_one_without_fx_row(self):
        quote = RemittanceQuoteService().create_quote(
            merchant=self.merchant,
            amount="100",
            from_currency="USD",
            to_currency="USD",
            fee_bearing="OUR",
            actor_type="ADMIN",
        )
        self.assertEqual(quote.exchange_rate, Decimal("1.00000000"))
        self.assertEqual(quote.rate_source, "SAME_CURRENCY")

    def test_missing_cross_currency_rate_fails_instead_of_using_one(self):
        with self.assertRaises(BusinessException) as caught:
            RemittanceQuoteService().create_quote(
                merchant=self.merchant,
                amount="100",
                from_currency="EUR",
                to_currency="KES",
                fee_bearing="OUR",
                actor_type="ADMIN",
            )
        self.assertEqual(caught.exception.code, "FX_RATE_UNAVAILABLE")

    def test_pending_suspended_and_expired_merchants_are_blocked(self):
        pending = Merchant.objects.create(
            merchant_no="MV2PENDING",
            merchant_name="Pending",
        )
        decision = RemittanceEligibilityPolicy().evaluate(pending)
        self.assertIn("MERCHANT_PENDING", [b.code for b in decision.blockers])

        MerchantLifecycleService().suspend(
            self.merchant,
            reason_code="TEST_SUSPEND",
            comment="test",
            actor="tests",
            source="TEST",
        )
        decision = RemittanceEligibilityPolicy().evaluate(self.merchant)
        self.assertIn("MERCHANT_SUSPENDED", [b.code for b in decision.blockers])

        self.merchant.refresh_from_db()
        self.merchant.license_expiry_date = timezone.localdate() - timedelta(days=1)
        self.merchant.save(update_fields=["license_expiry_date", "updated_at"])
        decision = RemittanceEligibilityPolicy().evaluate(self.merchant)
        self.assertIn("LICENSE_EXPIRED", [b.code for b in decision.blockers])

    def test_eligibility_does_not_require_customer_tariff(self):
        merchant = create_eligible_merchant("NOFEE")
        self.assertFalse(MerchantFee.objects.filter(merchant=merchant).exists())
        decision = RemittanceEligibilityPolicy().evaluate(merchant, Decimal("1000"))
        self.assertTrue(decision.eligible)

    def test_quote_ignores_customer_tariff_and_uses_global_fee(self):
        merchant = create_eligible_merchant("CUSTFEE", with_merchant_fee=True)
        quote = RemittanceQuoteService().create_quote(
            merchant=merchant,
            amount=Decimal("1000"),
            from_currency="USD",
            to_currency="USD",
            fee_bearing="OUR",
            actor_type="ADMIN",
        )
        self.assertEqual(quote.fee_amount, Decimal("5.00"))
        self.assertEqual(quote.fee_model, "PERCENTAGE")
        self.assertEqual(quote.fee_rate, Decimal("0.003000"))

    def test_quote_caps_at_maximum_fee(self):
        ensure_global_remittance_fee(fixed_fee=Decimal("2"), percent_rate=Decimal("10"), max_fee=Decimal("20"))
        quote = RemittanceQuoteService().create_quote(
            merchant=self.merchant,
            amount=Decimal("1000"),
            from_currency="USD",
            to_currency="USD",
            fee_bearing="OUR",
            actor_type="ADMIN",
        )
        self.assertEqual(quote.fee_amount, Decimal("20.00"))


class RemittanceApplicationTests(TestCase):
    def setUp(self):
        self.merchant = create_eligible_merchant("02", daily_limit=Decimal("1500"))

    def quote(self, amount="1000", actor_type="CUSTOMER", user_id="user-1"):
        return RemittanceQuoteService().create_quote(
            merchant=self.merchant,
            amount=amount,
            from_currency="USD",
            to_currency="USD",
            fee_bearing="OUR",
            actor_type=actor_type,
            user_id=user_id,
        )

    def test_submit_is_atomic_snapshot_bound_and_idempotent(self):
        quote = self.quote()
        payload = submit_payload(quote)
        service = RemittanceApplicationService()
        order, created = service.submit(
            merchant=self.merchant,
            payload=payload,
            idempotency_key="idem-same",
            user_id="user-1",
            actor_type="CUSTOMER",
        )
        retry, retry_created = service.submit(
            merchant=self.merchant,
            payload=payload,
            idempotency_key="idem-same",
            user_id="user-1",
            actor_type="CUSTOMER",
        )
        self.assertTrue(created)
        self.assertFalse(retry_created)
        self.assertEqual(order.pk, retry.pk)
        self.assertEqual(order.quote_id, quote.pk)
        self.assertEqual(order.user_id, "user-1")
        self.assertEqual(order.exchange_rate, quote.exchange_rate)
        self.assertEqual(order.sender_total_amount, quote.sender_total_amount)
        self.assertEqual(PaymentOrder.objects.count(), 1)
        self.assertEqual(FeeShare.objects.filter(payment_order=order).count(), 1)
        quote.refresh_from_db()
        self.assertEqual(quote.status, RemittanceQuote.QuoteStatus.USED)
        usage = MerchantDailyRemittanceUsage.objects.get(merchant=self.merchant)
        self.assertEqual(usage.total_amount, Decimal("1000.00"))
        self.assertEqual(usage.order_count, 1)

    def test_same_idempotency_key_with_different_payload_conflicts(self):
        quote = self.quote()
        payload = submit_payload(quote)
        service = RemittanceApplicationService()
        service.submit(
            merchant=self.merchant,
            payload=payload,
            idempotency_key="idem-conflict",
            user_id="user-1",
            actor_type="CUSTOMER",
        )
        changed = {**payload, "beneficiary_account": "DIFFERENT"}
        with self.assertRaises(BusinessException) as caught:
            service.submit(
                merchant=self.merchant,
                payload=changed,
                idempotency_key="idem-conflict",
                user_id="user-1",
                actor_type="CUSTOMER",
            )
        self.assertEqual(caught.exception.code, "IDEMPOTENCY_CONFLICT")

    def test_daily_limit_is_reserved_and_blocks_next_quote(self):
        quote = self.quote("1000")
        RemittanceApplicationService().submit(
            merchant=self.merchant,
            payload=submit_payload(quote),
            idempotency_key="idem-limit-1",
            user_id="user-1",
            actor_type="CUSTOMER",
        )
        with self.assertRaises(BusinessException) as caught:
            self.quote("600")
        self.assertEqual(caught.exception.code, "DAILY_LIMIT_EXCEEDED")

    def test_fee_share_failure_rolls_back_order_usage_and_quote(self):
        quote = self.quote()
        with patch(
            "apps.payment.services.remittance_application."
            "SettlementCalculator.calculate_fee_share",
            side_effect=RuntimeError("settlement unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                RemittanceApplicationService().submit(
                    merchant=self.merchant,
                    payload=submit_payload(quote),
                    idempotency_key="idem-rollback",
                    user_id="user-1",
                    actor_type="CUSTOMER",
                )
        self.assertFalse(PaymentOrder.objects.filter(idempotency_key="idem-rollback").exists())
        self.assertFalse(MerchantDailyRemittanceUsage.objects.filter(merchant=self.merchant).exists())
        quote.refresh_from_db()
        self.assertEqual(quote.status, RemittanceQuote.QuoteStatus.ACTIVE)

    def test_high_risk_exact_sanction_match_blocks_and_rolls_back(self):
        quote = self.quote()
        scan = {
            "name_hits": [{"risk_level": "HIGH", "match_type": "exact_name"}],
            "address_hits": [],
        }
        with patch(
            "apps.compliance.services.scan_entity_lightweight",
            return_value=scan,
        ):
            with self.assertRaises(BusinessException) as caught:
                RemittanceApplicationService().submit(
                    merchant=self.merchant,
                    payload=submit_payload(quote),
                    idempotency_key="idem-sanction",
                    user_id="user-1",
                    actor_type="CUSTOMER",
                )
        self.assertEqual(caught.exception.code, "SANCTION_BLOCKED")
        self.assertFalse(PaymentOrder.objects.exists())


@skipUnless(connection.vendor == "mysql", "并发行锁测试仅在 MySQL 执行")
class RemittanceConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_same_quote_creates_one_order(self):
        merchant = create_eligible_merchant("PG")
        quote = RemittanceQuoteService().create_quote(
            merchant=merchant,
            amount="100",
            from_currency="USD",
            to_currency="USD",
            fee_bearing="OUR",
            actor_type="ADMIN",
        )
        payload = submit_payload(quote)

        def submit():
            connections.close_all()
            current_merchant = Merchant.objects.get(pk=merchant.pk)
            current_quote = RemittanceQuote.objects.get(pk=quote.pk)
            try:
                order, _ = RemittanceApplicationService().submit(
                    merchant=current_merchant,
                    payload=submit_payload(current_quote),
                    idempotency_key="idem-concurrent",
                    actor_type="ADMIN",
                )
                return str(order.pk)
            except BusinessException as exc:
                return exc.code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: submit(), range(2)))
        self.assertEqual(PaymentOrder.objects.count(), 1)
        self.assertEqual(len(set(results)), 1)
