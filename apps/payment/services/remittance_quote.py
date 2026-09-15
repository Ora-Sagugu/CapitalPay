"""统一汇款报价：资格、费率、汇率和费用承担规则只在这里计算。"""
import hashlib
import json
import uuid
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from apps.core.exceptions import BusinessException
from apps.exchange.models import ExchangeRate
from apps.param.models import RemittanceFeeConfig
from apps.param.services import compute_remittance_fee
from apps.payment.models import RemittanceQuote

from .remittance_policy import RemittanceEligibilityPolicy


MONEY = Decimal("0.01")
RATE = Decimal("0.00000001")


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _payload_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class RemittanceQuoteService:
    QUOTE_TTL = timedelta(minutes=15)

    @staticmethod
    def _resolve_rate(from_currency: str, to_currency: str) -> tuple[Decimal, str]:
        if from_currency == to_currency:
            return Decimal("1").quantize(RATE), "SAME_CURRENCY"
        rate = ExchangeRate.objects.filter(
            date=timezone.localdate(),
            from_currency=from_currency,
            to_currency=to_currency,
            is_deleted=False,
        ).first()
        if not rate:
            raise BusinessException(
                "FX_RATE_UNAVAILABLE",
                f"No effective exchange rate is available for {from_currency}/{to_currency}; please retry later",
                503,
            )
        return Decimal(rate.rate).quantize(RATE), rate.source

    @staticmethod
    def _calculate_fee(amount: Decimal, fee_config: RemittanceFeeConfig) -> Decimal:
        return compute_remittance_fee(amount, fee_config)

    def create_quote(
        self,
        *,
        merchant,
        amount,
        from_currency: str,
        to_currency: str,
        fee_bearing: str,
        actor_type: str,
        user_id: str = "",
    ) -> RemittanceQuote:
        amount = _money(Decimal(str(amount)))
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        if fee_bearing not in {"OUR", "SHA", "BEN"}:
            raise BusinessException("FEE_BEARING_INVALID", "The charge-bearing method is invalid", 400)

        RemittanceEligibilityPolicy().assert_eligible(merchant, amount)
        fee_config = RemittanceFeeConfig.get_config()
        fee = self._calculate_fee(amount, fee_config)
        exchange_rate, rate_source = self._resolve_rate(from_currency, to_currency)

        if fee_bearing == "OUR":
            sender_fee = fee
            beneficiary_fee = Decimal("0")
            _split_branch = "OUR"
        elif fee_bearing == "SHA":
            sender_fee = _money(fee / 2)
            beneficiary_fee = fee - sender_fee
            _split_branch = "SHA"
        else:
            sender_fee = Decimal("0")
            beneficiary_fee = fee
            _split_branch = "BEN"

        beneficiary_principal = amount - beneficiary_fee
        if beneficiary_principal <= 0:
            raise BusinessException(
                "FEE_EXCEEDS_AMOUNT",
                "Charges must not equal or exceed the remittance principal",
                422,
            )
        sender_total = _money(amount + sender_fee)
        settle_amount = _money(beneficiary_principal * exchange_rate)

        digest_payload = {
            "merchant": merchant.merchant_no,
            "amount": str(amount),
            "from_currency": from_currency,
            "to_currency": to_currency,
            "fee_bearing": fee_bearing,
            "fee_config": str(fee_config.id),
            "fee_updated_at": fee_config.updated_at.isoformat(),
            "rate": str(exchange_rate),
            "rate_source": rate_source,
        }
        return RemittanceQuote.objects.create(
            quote_no=f"RQT{timezone.now():%Y%m%d%H%M%S}{uuid.uuid4().hex[:10].upper()}",
            merchant=merchant,
            user_id=user_id,
            actor_type=actor_type,
            amount=amount,
            from_currency=from_currency,
            to_currency=to_currency,
            fee_bearing=fee_bearing,
            fee_currency=from_currency,
            fee_amount=fee,
            sender_fee_amount=sender_fee,
            beneficiary_fee_amount=beneficiary_fee,
            sender_total_amount=sender_total,
            settle_amount=settle_amount,
            exchange_rate=exchange_rate,
            rate_source=rate_source,
            fee_model="PERCENTAGE",
            fee_rate=(Decimal(str(fee_config.percent_rate or 0)) / Decimal("100")).quantize(RATE),
            fixed_fee=fee_config.fixed_fee or 0,
            payload_hash=_payload_hash(digest_payload),
            expires_at=timezone.now() + self.QUOTE_TTL,
        )

    @staticmethod
    def serialize(quote: RemittanceQuote) -> dict:
        return {
            "quote_id": quote.quote_no,
            "merchant_no": quote.merchant.merchant_no,
            "merchant_name": quote.merchant.merchant_name,
            "amount": str(quote.amount),
            "from_currency": quote.from_currency,
            "to_currency": quote.to_currency,
            "fee_bearing": quote.fee_bearing,
            "fee_currency": quote.fee_currency,
            "fee_model": quote.fee_model,
            "fee_rate": str(quote.fee_rate),
            "fee_rate_percent": str(
                (quote.fee_rate * Decimal("100")).quantize(Decimal("0.0001"))
            ),
            "fixed_fee": str(quote.fixed_fee),
            "total_fee": str(quote.fee_amount),
            "sender_fee": str(quote.sender_fee_amount),
            "beneficiary_fee": str(quote.beneficiary_fee_amount),
            "sender_total": str(quote.sender_total_amount),
            "settle_amount": str(quote.settle_amount),
            "exchange_rate": str(quote.exchange_rate),
            "rate_source": quote.rate_source,
            "expires_at": quote.expires_at,
            "fee_formula": (
                f"{quote.fee_bearing}: principal {quote.amount}, charges {quote.fee_amount} "
                f"{quote.fee_currency}"
            ),
        }
