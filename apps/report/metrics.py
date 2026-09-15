"""第一阶段经营分析指标口径。

本模块是报表/分析接口的单一事实来源。金额一律 Decimal 字符串、按币种拆分，
禁止跨币种合计。指标均为「系统记录口径」，不等于银行真实到账或已实现利润。
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from django.conf import settings

from apps.payment.models import PaymentOrder, RefundOrder


MONEY_QUANT = Decimal("0.01")

TIME_BASIS_CREATED = "created_at"
TIME_BASIS_RECEIVED = "pay_received_at"
TIME_BASIS_REFUNDED = "refunded_at"
TIME_BASIS_SETTLED = "settled_at"

TIME_BASIS_CHOICES = (
    TIME_BASIS_CREATED,
    TIME_BASIS_RECEIVED,
    TIME_BASIS_REFUNDED,
    TIME_BASIS_SETTLED,
)

TIME_BASIS_FIELDS = {
    TIME_BASIS_CREATED: "created_at",
    TIME_BASIS_RECEIVED: "pay_received_at",
    TIME_BASIS_REFUNDED: "refunded_at",
    TIME_BASIS_SETTLED: "settled_at",
}

PENDING_REVIEW_STATUSES = (PaymentOrder.OrderStatus.PENDING_REVIEW,)
PENDING_PAY_STATUSES = (
    PaymentOrder.OrderStatus.PENDING_PAY,
    PaymentOrder.OrderStatus.PRE_CREATE,
    PaymentOrder.OrderStatus.PROCESSING,
)
PENDING_SETTLE_STATUSES = (PaymentOrder.OrderStatus.PENDING_SETTLE,)

CONFIRMED_COLLECTION_STATUSES = (
    PaymentOrder.OrderStatus.PAY_RECEIVED,
    PaymentOrder.OrderStatus.PENDING_SETTLE,
    PaymentOrder.OrderStatus.SETTLED,
    PaymentOrder.OrderStatus.COMPLETED,
    PaymentOrder.OrderStatus.REFUNDING,
    PaymentOrder.OrderStatus.REFUNDED,
)

SUCCESS_REFUND_STATUS = RefundOrder.RefundStatus.SUCCESS

EVIDENCE_SYSTEM_RECORD = "SYSTEM_RECORD"
EVIDENCE_BANK_CONFIRMED = "BANK_CONFIRMED"
EVIDENCE_UNVERIFIED = "UNVERIFIED"

UNLINKED_USER_KEY = "__unlinked__"
UNLINKED_USER_LABEL = "Unlinked user"

BREAKDOWN_DIMENSIONS = ("merchant", "user", "agent", "channel", "status", "currency")

CAVEATS = (
    "Amounts are disaggregated by currency and must not be summed across currencies.",
    "System-confirmed collection means pay_received_at has been written; it does not constitute bank-funds receipt.",
    "SETTLED is established only after a successful correspondent payout and a posted money movement; batch creation is not final settlement.",
    "Fee share is an estimate, not booked platform profit or paid agent commission.",
    "Orders lacking a user_id are classified as Unlinked user, with coverage disclosed separately.",
    "Beneficiary account numbers are masked by default, including in exports.",
)


def business_timezone_name() -> str:
    return getattr(settings, "TIME_ZONE", "Africa/Nairobi") or "Africa/Nairobi"


def max_range_days() -> int:
    return int(getattr(settings, "REPORT_MAX_RANGE_DAYS", 180))


def max_page_size() -> int:
    return int(getattr(settings, "REPORT_MAX_PAGE_SIZE", 100))


def max_export_rows() -> int:
    return int(getattr(settings, "REPORT_MAX_EXPORT_ROWS", 2000))


def money_str(value) -> str:
    if value is None or value == "":
        return "0.00"
    return str(Decimal(str(value)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))


def ratio_str(numerator: int, denominator: int) -> str:
    if not denominator:
        return "0.0000"
    return str((Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.0001")))


def mask_account(account: str | None) -> str:
    raw = (account or "").strip()
    if not raw:
        return ""
    if len(raw) <= 4:
        return "****"
    return f"****{raw[-4:]}"


def excel_safe(value):
    """Prevent Excel formula injection on exported text cells."""
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@"}:
        return f"'{value}"
    return value


def currency_of_order(order) -> str:
    return (getattr(order, "from_currency", None) or getattr(order, "currency", None) or "") or ""


def empty_money_bucket(currency: str, count: int = 0) -> dict:
    return {
        "currency": currency or "",
        "count": count,
        "amount": "0.00",
        "fee_amount": "0.00",
    }


def merge_money_rows(rows: Iterable[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for row in rows:
        currency = row.get("currency") or ""
        bucket = merged.setdefault(currency, empty_money_bucket(currency))
        bucket["count"] += int(row.get("count") or 0)
        bucket["amount"] = money_str(Decimal(bucket["amount"]) + Decimal(str(row.get("amount") or 0)))
        bucket["fee_amount"] = money_str(
            Decimal(bucket["fee_amount"]) + Decimal(str(row.get("fee_amount") or 0))
        )
    return [merged[key] for key in sorted(merged)]


def contract_payload(*, time_basis: str, date_from, date_to, start_dt, end_dt) -> dict:
    return {
        "timezone": business_timezone_name(),
        "time_basis": time_basis,
        "date_from": str(date_from),
        "date_to": str(date_to),
        "range_start": start_dt.isoformat(),
        "range_end_exclusive": end_dt.isoformat(),
        "amount_format": "decimal_string",
        "cross_currency_sum": False,
        "evidence_level": EVIDENCE_SYSTEM_RECORD,
        "caveats": list(CAVEATS),
    }
