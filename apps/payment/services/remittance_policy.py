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


def _as_limit(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


class RemittanceEligibilityPolicy:
    """按商户和金额评估是否允许创建新的汇款申请。"""

    def evaluate(
        self,
        merchant: Merchant,
        amount: Decimal | None = None,
        *,
        include_usage: bool = True,
        customer=None,
        require_customer: bool = False,
    ) -> EligibilityDecision:
        blockers: list[EligibilityBlocker] = []
        today = timezone.localdate()

        if require_customer or customer is not None:
            if not customer or getattr(customer, "is_deleted", False):
                blockers.append(EligibilityBlocker(
                    "CUSTOMER_NOT_FOUND", "The customer does not exist", "customer",
                ))
            elif customer.merchant_id != getattr(merchant, "id", None):
                blockers.append(EligibilityBlocker(
                    "MERCHANT_CUSTOMER_FORBIDDEN",
                    "This customer is not assigned to the current merchant",
                    "customer",
                ))
            # Merchant-owned customers are remittable on create — no separate KYC gate.

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

        # Settlement banks may be configured later. Remittances debit CURRENT book.

        if amount is not None:
            amount = Decimal(str(amount))
            if amount <= 0:
                blockers.append(EligibilityBlocker(
                    "AMOUNT_INVALID", "The remittance principal must be greater than zero", "amount"
                ))
            max_single = _as_limit(merchant.max_single_amount)
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
                daily_limit = _as_limit(merchant.daily_limit)
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
        customer=None,
        require_customer: bool = False,
    ) -> None:
        decision = self.evaluate(
            merchant,
            amount,
            include_usage=include_usage,
            customer=customer,
            require_customer=require_customer,
        )
        if decision.blockers:
            blocker = decision.blockers[0]
            raise BusinessException(blocker.code, blocker.message, 422)

    @staticmethod
    def assert_can_continue_existing(merchant: Merchant) -> None:
        """既有在途订单可在普通暂停下继续，但关闭/制裁/BLOCKED 必须阻断。"""
        if merchant is None:
            return
        if merchant.is_deleted or merchant.status == Merchant.Status.CLOSED:
            raise BusinessException("MERCHANT_CLOSED", "The customer has been closed; the instruction requires manual handling", 422)
        if merchant.risk_level == "BLOCKED":
            raise BusinessException("MERCHANT_RISK_BLOCKED", "The customer's risk classification prohibits continuation of this instruction", 422)
        if merchant.sanction_status != "UN":
            raise BusinessException("MERCHANT_SANCTIONED", "The customer is subject to sanctions restrictions", 422)


class AgentRemittanceEligibilityPolicy:
    """Eligibility for remittances booked on the Agent CURRENT ledger."""

    def evaluate(self, agent, customer, amount: Decimal | None = None, *, include_usage: bool = True) -> EligibilityDecision:
        from apps.agent.models import Agent, AgentCustomer, AgentKYC
        from apps.payment.models import AgentDailyRemittanceUsage

        blockers: list[EligibilityBlocker] = []
        today = timezone.localdate()

        if not agent or getattr(agent, "is_deleted", False):
            blockers.append(EligibilityBlocker("AGENT_NOT_FOUND", "The agent does not exist or has been closed", "agent"))
        elif agent.status != "ACTIVE":
            blockers.append(EligibilityBlocker("AGENT_INACTIVE", "The agent is not presently authorised to transact", "agent"))
        else:
            try:
                kyc_status = agent.kyc.kyc_status
            except AgentKYC.DoesNotExist:
                kyc_status = ""
            if kyc_status != AgentKYC.KycStatus.APPROVED:
                blockers.append(EligibilityBlocker(
                    "AGENT_KYC_NOT_APPROVED",
                    "Agent due diligence (KYC) has not been approved",
                    "agent",
                ))

        if not customer or getattr(customer, "is_deleted", False):
            blockers.append(EligibilityBlocker("CUSTOMER_NOT_FOUND", "The customer does not exist", "customer"))
        elif customer.agent_id != getattr(agent, "id", None):
            blockers.append(EligibilityBlocker(
                "AGENT_CUSTOMER_FORBIDDEN",
                "This customer is not assigned to the current agent",
                "customer",
            ))
        # Profile customers are remittable once created — no separate KYC gate.
        if amount is not None:
            amount = Decimal(str(amount))
            if amount <= 0:
                blockers.append(EligibilityBlocker(
                    "AMOUNT_INVALID", "The remittance principal must be greater than zero", "amount"
                ))
            max_single = getattr(agent, "max_single_amount", None) if agent else None
            if max_single is not None and amount > Decimal(str(max_single)):
                blockers.append(EligibilityBlocker(
                    "AMOUNT_LIMIT_EXCEEDED",
                    f"The remittance principal exceeds the per-transaction limit of {max_single}",
                    "amount",
                ))
            if include_usage and agent:
                usage = AgentDailyRemittanceUsage.objects.filter(
                    agent=agent, usage_date=today, is_deleted=False,
                ).first()
                used_amount = usage.total_amount if usage else Decimal("0")
                daily_limit = getattr(agent, "daily_limit", None)
                if daily_limit is not None and used_amount + amount > Decimal(str(daily_limit)):
                    blockers.append(EligibilityBlocker(
                        "DAILY_LIMIT_EXCEEDED",
                        f"Insufficient remaining daily remittance capacity; the daily limit is {daily_limit}",
                        "amount",
                    ))

        return EligibilityDecision(eligible=not blockers, blockers=blockers)

    def assert_eligible(self, agent, customer, amount: Decimal | None = None, *, include_usage: bool = True) -> None:
        decision = self.evaluate(agent, customer, amount, include_usage=include_usage)
        if decision.blockers:
            blocker = decision.blockers[0]
            raise BusinessException(blocker.code, blocker.message, 422)

    @staticmethod
    def assert_can_continue_existing(agent) -> None:
        if agent is None:
            return
        if getattr(agent, "is_deleted", False) or agent.status == "CLOSED":
            raise BusinessException("AGENT_INACTIVE", "The agent is not presently authorised to transact", 422)
