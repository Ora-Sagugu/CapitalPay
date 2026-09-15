"""汇款资格策略 — 预览、提交和执行共享同一套业务门槛。"""
from dataclasses import dataclass, field
from decimal import Decimal

from django.utils import timezone

from apps.core.exceptions import BusinessException
from apps.merchant.models import (
    Merchant,
    MerchantFee,
    MerchantKYC,
    MerchantPaymentProduct,
    MerchantSettlementAccount,
)
from apps.payment.models import MerchantDailyRemittanceUsage


@dataclass(frozen=True)
class EligibilityBlocker:
    code: str
    message: str
    field: str = "merchant"

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "field": self.field}


@dataclass(frozen=True)
class EligibilityDecision:
    eligible: bool
    blockers: list[EligibilityBlocker] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "eligible": self.eligible,
            "blockers": [blocker.as_dict() for blocker in self.blockers],
        }


def _strictest_limit(*values) -> Decimal | None:
    limits = [Decimal(str(value)) for value in values if value is not None]
    return min(limits) if limits else None


class RemittanceEligibilityPolicy:
    """按商户和金额评估是否允许创建新的汇款申请。"""

    def evaluate(
        self,
        merchant: Merchant,
        amount: Decimal | None = None,
        *,
        include_usage: bool = True,
    ) -> EligibilityDecision:
        blockers: list[EligibilityBlocker] = []
        today = timezone.localdate()

        if merchant.is_deleted:
            blockers.append(EligibilityBlocker("MERCHANT_NOT_FOUND", "The customer does not exist or has been closed"))
        elif merchant.status == Merchant.Status.PENDING:
            blockers.append(EligibilityBlocker("MERCHANT_PENDING", "The customer has not completed customer due diligence (KYC) and product admission review"))
        elif merchant.status == Merchant.Status.SUSPENDED:
            message = "The customer is suspended from transacting"
            if merchant.status_reason_code == "LICENSE_EXPIRED":
                message = "The business licence has expired; the customer is suspended from transacting"
            blockers.append(EligibilityBlocker("MERCHANT_SUSPENDED", message))
        elif merchant.status == Merchant.Status.CLOSED:
            blockers.append(EligibilityBlocker("MERCHANT_CLOSED", "The customer has been closed"))
        elif merchant.status != Merchant.Status.ACTIVE:
            blockers.append(EligibilityBlocker("MERCHANT_INACTIVE", "The customer is not presently authorised to transact"))

        try:
            kyc_status = merchant.kyc.kyc_status
        except MerchantKYC.DoesNotExist:
            kyc_status = ""
        if kyc_status != MerchantKYC.Status.APPROVED:
            blockers.append(EligibilityBlocker("KYC_NOT_APPROVED", "Customer due diligence (KYC) has not been approved"))

        if not merchant.license_expiry_date:
            blockers.append(EligibilityBlocker("LICENSE_REQUIRED", "The business-licence expiry date has not been recorded"))
        elif merchant.license_expiry_date < today:
            blockers.append(EligibilityBlocker(
                "LICENSE_EXPIRED",
                f"The business licence expired on {merchant.license_expiry_date}",
            ))

        if merchant.risk_level == "BLOCKED":
            blockers.append(EligibilityBlocker("MERCHANT_RISK_BLOCKED", "The customer's risk rating prohibits transacting"))
        if merchant.sanction_status != "UN":
            blockers.append(EligibilityBlocker("MERCHANT_SANCTIONED", "The customer is subject to sanctions restrictions"))
        from django.conf import settings
        if getattr(settings, "ENABLE_AGENTS", True):
            if merchant.agent_id and getattr(merchant.agent, "status", "ACTIVE") != "ACTIVE":
                blockers.append(EligibilityBlocker("AGENT_INACTIVE", "The affiliated agent is not presently authorised to transact"))

        prefetched_products = getattr(merchant, "_remittance_products", None)
        product = (
            prefetched_products[0]
            if prefetched_products
            else None
            if prefetched_products is not None
            else MerchantPaymentProduct.objects.filter(
                merchant=merchant,
                product_type=MerchantFee.ProductType.WIRE_TRANSFER,
                is_deleted=False,
            ).first()
        )
        if not product or not product.is_enabled:
            blockers.append(EligibilityBlocker("PRODUCT_NOT_ENABLED", "The remittance product has not been enabled"))

        prefetched_accounts = getattr(merchant, "_default_settlement_accounts", None)
        has_settlement_account = (
            bool(prefetched_accounts)
            if prefetched_accounts is not None
            else MerchantSettlementAccount.objects.filter(
                merchant=merchant, is_default=True, is_deleted=False
            ).exists()
        )
        if not has_settlement_account:
            blockers.append(EligibilityBlocker(
                "SETTLEMENT_ACCOUNT_REQUIRED", "A default settlement account has not been configured"
            ))

        if amount is not None:
            amount = Decimal(str(amount))
            if amount <= 0:
                blockers.append(EligibilityBlocker(
                    "AMOUNT_INVALID", "The remittance principal must be greater than zero", "amount"
                ))
            max_single = _strictest_limit(
                merchant.max_single_amount,
                product.max_single_amount if product else None,
            )
            if max_single is not None and amount > max_single:
                blockers.append(EligibilityBlocker(
                    "AMOUNT_LIMIT_EXCEEDED",
                    f"The remittance principal exceeds the per-transaction limit of {max_single}",
                    "amount",
                ))

            if include_usage:
                usage = MerchantDailyRemittanceUsage.objects.filter(
                    merchant=merchant, usage_date=today, is_deleted=False
                ).first()
                used_amount = usage.total_amount if usage else Decimal("0")
                used_count = usage.order_count if usage else 0
                daily_limit = _strictest_limit(
                    merchant.daily_limit,
                    product.daily_limit if product else None,
                )
                if daily_limit is not None and used_amount + amount > daily_limit:
                    blockers.append(EligibilityBlocker(
                        "DAILY_LIMIT_EXCEEDED",
                        f"Insufficient remaining daily remittance capacity; the daily limit is {daily_limit}",
                        "amount",
                    ))
                if merchant.daily_count is not None and used_count + 1 > merchant.daily_count:
                    blockers.append(EligibilityBlocker(
                        "DAILY_COUNT_EXCEEDED",
                        f"The daily remittance count has reached the limit of {merchant.daily_count}",
                        "amount",
                    ))

        return EligibilityDecision(eligible=not blockers, blockers=blockers)

    def assert_eligible(
        self,
        merchant: Merchant,
        amount: Decimal | None = None,
        *,
        include_usage: bool = True,
    ) -> None:
        decision = self.evaluate(merchant, amount, include_usage=include_usage)
        if decision.blockers:
            blocker = decision.blockers[0]
            raise BusinessException(blocker.code, blocker.message, 422)

    @staticmethod
    def assert_can_continue_existing(merchant: Merchant) -> None:
        """既有在途订单可在普通暂停下继续，但关闭/制裁/BLOCKED 必须阻断。"""
        if merchant.is_deleted or merchant.status == Merchant.Status.CLOSED:
            raise BusinessException("MERCHANT_CLOSED", "The customer has been closed; the instruction requires manual handling", 422)
        if merchant.risk_level == "BLOCKED":
            raise BusinessException("MERCHANT_RISK_BLOCKED", "The customer's risk classification prohibits continuation of this instruction", 422)
        if merchant.sanction_status != "UN":
            raise BusinessException("MERCHANT_SANCTIONED", "The customer is subject to sanctions restrictions", 422)
