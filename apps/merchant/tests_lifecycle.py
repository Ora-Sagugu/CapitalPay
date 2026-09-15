from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.core.exceptions import BusinessException
from apps.merchant.models import (
    Merchant,
    MerchantFee,
    MerchantKYC,
    MerchantPaymentProduct,
    MerchantSettlementAccount,
    MerchantStatusEvent,
)
from apps.merchant.services import MerchantLifecycleService, MerchantService


def configured_pending_merchant(suffix="01", *, with_settlement=True):
    merchant = Merchant.objects.create(
        merchant_no=f"MLC{suffix}",
        merchant_name=f"Lifecycle {suffix}",
        license_expiry_date=timezone.localdate() + timedelta(days=365),
        risk_level="LOW",
        sanction_status="UN",
    )
    MerchantKYC.objects.create(
        merchant=merchant,
        legal_person="Owner",
        id_number="encrypted",
        business_license="encrypted",
        kyc_status=MerchantKYC.Status.APPROVED,
    )
    MerchantPaymentProduct.objects.create(
        merchant=merchant,
        product_type=MerchantFee.ProductType.WIRE_TRANSFER,
        is_enabled=True,
        max_single_amount=Decimal("1000"),
        daily_limit=Decimal("5000"),
    )
    if with_settlement:
        MerchantSettlementAccount.objects.create(
            merchant=merchant,
            bank_name="Bank",
            account_name=merchant.merchant_name,
            account_number="encrypted",
            is_default=True,
        )
    return merchant


class MerchantLifecycleTests(TestCase):
    def test_new_merchant_is_pending_and_has_initial_event(self):
        merchant = Merchant.objects.create(merchant_name="New Merchant")
        self.assertEqual(merchant.status, Merchant.Status.PENDING)
        event = MerchantStatusEvent.objects.get(merchant=merchant)
        self.assertEqual(event.to_status, Merchant.Status.PENDING)
        self.assertEqual(event.reason_code, "MERCHANT_CREATED")

    def test_direct_existing_status_write_is_rejected(self):
        merchant = Merchant.objects.create(merchant_name="Guarded Merchant")
        merchant.status = Merchant.Status.ACTIVE
        with self.assertRaises(RuntimeError):
            merchant.save(update_fields=["status", "updated_at"])

    def test_valid_transitions_are_audited_and_closed_is_terminal(self):
        merchant = configured_pending_merchant()
        service = MerchantLifecycleService()
        merchant = service.activate(
            merchant,
            reason_code="APPROVED",
            comment="approved",
            actor="reviewer",
            source="TEST",
        )
        merchant = service.suspend(
            merchant,
            reason_code="MANUAL",
            comment="pause",
            actor="reviewer",
            source="TEST",
        )
        merchant = service.close(
            merchant,
            reason_code="CLOSED",
            comment="closed",
            actor="reviewer",
            source="TEST",
        )
        self.assertEqual(merchant.status, Merchant.Status.CLOSED)
        self.assertEqual(
            list(
                MerchantStatusEvent.objects.filter(merchant=merchant)
                .order_by("created_at")
                .values_list("to_status", flat=True)
            ),
            ["PENDING", "ACTIVE", "SUSPENDED", "CLOSED"],
        )
        with self.assertRaises(BusinessException) as caught:
            service.activate(
                merchant,
                reason_code="INVALID",
                comment="must fail",
                actor="reviewer",
                source="TEST",
            )
        self.assertEqual(caught.exception.code, "MERCHANT_STATUS_TRANSITION_INVALID")

    def test_activation_reports_missing_prerequisite(self):
        merchant = Merchant.objects.create(
            merchant_name="Incomplete",
            license_expiry_date=timezone.localdate() + timedelta(days=1),
        )
        with self.assertRaises(BusinessException) as caught:
            MerchantLifecycleService().activate(
                merchant,
                reason_code="INVALID",
                comment="must fail",
                actor="reviewer",
                source="TEST",
            )
        self.assertEqual(caught.exception.code, "KYC_NOT_APPROVED")

    def test_kyc_approval_allowed_without_settlement_account(self):
        """Settlement banks may be set later; KYC may still activate."""
        merchant = Merchant.objects.create(
            merchant_no="MLCROLLBACK",
            merchant_name="Rollback",
            license_expiry_date=timezone.localdate() + timedelta(days=365),
        )
        kyc = MerchantKYC.objects.create(
            merchant=merchant,
            legal_person="Owner",
            id_number="encrypted",
            business_license="encrypted",
            kyc_status=MerchantKYC.Status.PENDING,
        )
        MerchantService().review_kyc(
            merchant,
            {
                "action": "approve",
                "risk_level": "LOW",
                "fee_model": MerchantFee.FeeModel.PERCENTAGE,
                "fee_rate": Decimal("0.003"),
                "fixed_fee": Decimal("0"),
                "min_fee": Decimal("0"),
                "max_fee": None,
                "max_single_amount": Decimal("1000"),
                "daily_limit": Decimal("5000"),
                "daily_count": 5,
                "reason": "",
            },
            actor="reviewer",
        )
        merchant.refresh_from_db()
        kyc.refresh_from_db()
        self.assertEqual(merchant.status, Merchant.Status.ACTIVE)
        self.assertEqual(kyc.kyc_status, MerchantKYC.Status.APPROVED)
        self.assertFalse(merchant.settlement_accounts.filter(is_deleted=False).exists())
        self.assertTrue(MerchantFee.objects.filter(merchant=merchant).exists())
        self.assertTrue(MerchantPaymentProduct.objects.filter(merchant=merchant).exists())

    def test_kyc_approval_does_not_pre_open_virtual_accounts(self):
        merchant = Merchant.objects.create(
            merchant_no="MLCVA01",
            merchant_name="VA Opt In",
            license_expiry_date=timezone.localdate() + timedelta(days=365),
            risk_level="LOW",
        )
        MerchantKYC.objects.create(
            merchant=merchant,
            legal_person="Owner",
            id_number="encrypted",
            business_license="encrypted",
            kyc_status=MerchantKYC.Status.PENDING,
        )
        MerchantSettlementAccount.objects.create(
            merchant=merchant,
            bank_name="Bank",
            account_name=merchant.merchant_name,
            account_number="encrypted",
            is_default=True,
        )
        MerchantService().review_kyc(
            merchant,
            {
                "action": "approve",
                "risk_level": "LOW",
                "fee_model": MerchantFee.FeeModel.PERCENTAGE,
                "fee_rate": Decimal("0.003"),
                "fixed_fee": Decimal("0"),
                "min_fee": Decimal("0"),
                "max_fee": None,
                "max_single_amount": Decimal("1000"),
                "daily_limit": Decimal("5000"),
                "daily_count": 5,
                "reason": "",
            },
            actor="reviewer",
        )
        merchant.refresh_from_db()
        self.assertEqual(merchant.status, Merchant.Status.ACTIVE)
        self.assertFalse(merchant.virtual_accounts.filter(is_deleted=False).exists())
