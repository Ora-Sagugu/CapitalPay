"""经营分析聚合服务 — 按指标口径筛选、汇总、下钻。"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Count, Q, Sum, Value
from django.db.models.functions import Coalesce, NullIf, TruncDate
from django.utils import timezone
from django.utils.timezone import get_current_timezone

from apps.account.models import MoneyMovement, VaLedgerEntry
from apps.core.exceptions import BusinessException
from apps.payment.models import PaymentOrder, RefundOrder
from apps.payment.services.fund_trace import resolve_collection_va, trace_fund, FundTraceNotFound
from apps.reconciliation.models import ReconciliationDiff
from apps.routing.models import RoutingLog
from apps.settlement.models import FeeShare, SettlementDetail
from .metrics import (
    BREAKDOWN_DIMENSIONS,
    CONFIRMED_COLLECTION_STATUSES,
    PENDING_PAY_STATUSES,
    PENDING_REVIEW_STATUSES,
    PENDING_SETTLE_STATUSES,
    SUCCESS_REFUND_STATUS,
    TIME_BASIS_CHOICES,
    TIME_BASIS_CREATED,
    TIME_BASIS_RECEIVED,
    TIME_BASIS_REFUNDED,
    TIME_BASIS_SETTLED,
    UNLINKED_USER_KEY,
    UNLINKED_USER_LABEL,
    business_timezone_name,
    contract_payload,
    excel_safe,
    mask_account,
    max_export_rows,
    max_page_size,
    max_range_days,
    money_str,
    ratio_str,
)


class AnalyticsQueryError(BusinessException):
    """分析查询参数错误。"""


def _tz():
    return ZoneInfo(business_timezone_name())


def parse_filters(payload: dict) -> dict:
    """解析并校验筛选。日期采用 [start, end_exclusive)。"""
    payload = payload or {}
    date_from = payload.get("date_from") or payload.get("start_date")
    date_to = payload.get("date_to") or payload.get("end_date")
    if not date_from or not date_to:
        raise AnalyticsQueryError("INVALID_DATE_RANGE", "A start date and an end date must be selected", 400)

    if isinstance(date_from, str):
        try:
            date_from = datetime.strptime(date_from[:10], "%Y-%m-%d").date()
        except ValueError as exc:
            raise AnalyticsQueryError("INVALID_DATE_FORMAT", "The date format must be YYYY-MM-DD", 400) from exc
    if isinstance(date_to, str):
        try:
            date_to = datetime.strptime(date_to[:10], "%Y-%m-%d").date()
        except ValueError as exc:
            raise AnalyticsQueryError("INVALID_DATE_FORMAT", "The date format must be YYYY-MM-DD", 400) from exc

    if date_to < date_from:
        raise AnalyticsQueryError("INVALID_DATE_RANGE", "The end date must not precede the start date", 400)
    span = (date_to - date_from).days + 1
    if span > max_range_days():
        raise AnalyticsQueryError(
            "DATE_RANGE_TOO_LARGE",
            f"The query interval cannot exceed {max_range_days()} days",
            400,
        )

    time_basis = (payload.get("time_basis") or TIME_BASIS_CREATED).strip()
    if time_basis not in TIME_BASIS_CHOICES:
        raise AnalyticsQueryError("INVALID_TIME_BASIS", "The specified time basis is not supported", 400)

    tz = _tz()
    start_dt = datetime.combine(date_from, time.min, tzinfo=tz)
    end_dt = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=tz)

    page = int(payload.get("page") or 1)
    page_size = int(payload.get("page_size") or 20)
    if page < 1:
        page = 1
    page_size = min(max(page_size, 1), max_page_size())

    dimension = (payload.get("dimension") or "merchant").strip()
    if dimension not in BREAKDOWN_DIMENSIONS:
        raise AnalyticsQueryError("INVALID_DIMENSION", "The specified analysis dimension is not supported", 400)

    statuses = payload.get("status") or payload.get("statuses") or []
    if isinstance(statuses, str) and statuses:
        statuses = [s.strip() for s in statuses.split(",") if s.strip()]
    elif not isinstance(statuses, (list, tuple)):
        statuses = []

    return {
        "date_from": date_from,
        "date_to": date_to,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "time_basis": time_basis,
        "merchant_id": payload.get("merchant_id") or "",
        "agent_id": payload.get("agent_id") or "",
        "user_id": (payload.get("user_id") or "").strip(),
        "bank_code": (payload.get("bank_code") or payload.get("bank_name") or "").strip(),
        "from_currency": (payload.get("from_currency") or "").strip().upper(),
        "to_currency": (payload.get("to_currency") or "").strip().upper(),
        "statuses": list(statuses),
        "order_no": (payload.get("order_no") or "").strip(),
        "unique_identification_no": (payload.get("unique_identification_no") or payload.get("uin") or "").strip(),
        "prn_code": (payload.get("prn_code") or "").strip(),
        "page": page,
        "page_size": page_size,
        "dimension": dimension,
        "exact_lookup": bool(
            (payload.get("order_no") or "").strip()
            or (payload.get("unique_identification_no") or payload.get("uin") or "").strip()
            or (payload.get("prn_code") or "").strip()
        ),
    }


def _apply_common_filters(qs, filters: dict, *, skip_date: bool = False):
    if not skip_date:
        field = {
            TIME_BASIS_CREATED: "created_at",
            TIME_BASIS_RECEIVED: "pay_received_at",
            TIME_BASIS_SETTLED: "settled_at",
            TIME_BASIS_REFUNDED: "created_at",
        }[filters["time_basis"]]
        qs = qs.filter(**{f"{field}__gte": filters["start_dt"], f"{field}__lt": filters["end_dt"]})
    if filters["merchant_id"]:
        qs = qs.filter(merchant_id=filters["merchant_id"])
    if filters["agent_id"]:
        qs = qs.filter(merchant__agent_id=filters["agent_id"])
    if filters["user_id"]:
        qs = qs.filter(user_id=filters["user_id"])
    if filters["bank_code"]:
        qs = qs.filter(bank_code=filters["bank_code"])
    if filters["from_currency"]:
        qs = qs.filter(from_currency=filters["from_currency"])
    if filters["to_currency"]:
        qs = qs.filter(to_currency=filters["to_currency"])
    if filters["statuses"]:
        qs = qs.filter(status__in=filters["statuses"])
    if filters["order_no"]:
        qs = qs.filter(order_no=filters["order_no"])
    if filters["unique_identification_no"]:
        qs = qs.filter(unique_identification_no=filters["unique_identification_no"])
    if filters["prn_code"]:
        qs = qs.filter(prn_code=filters["prn_code"])
    return qs


def order_queryset(filters: dict):
    qs = PaymentOrder.objects.filter(is_deleted=False).select_related("merchant", "merchant__agent")
    return _apply_common_filters(qs, filters, skip_date=bool(filters["exact_lookup"]))


def _group_currency(qs, amount_field="amount", extra_fee="fee_amount"):
    rows = (
        qs.values("from_currency")
        .annotate(
            count=Count("id"),
            amount=Coalesce(Sum(amount_field), Value(Decimal("0.00"))),
            fee_amount=Coalesce(Sum(extra_fee), Value(Decimal("0.00"))),
        )
        .order_by("from_currency")
    )
    return [
        {
            "currency": row["from_currency"] or "",
            "count": row["count"],
            "amount": money_str(row["amount"]),
            "fee_amount": money_str(row["fee_amount"]),
        }
        for row in rows
    ]


def _aging(qs) -> dict:
    now = timezone.now()
    return {
        "0_1d": qs.filter(created_at__gte=now - timedelta(days=1)).count(),
        "1_3d": qs.filter(created_at__lt=now - timedelta(days=1), created_at__gte=now - timedelta(days=3)).count(),
        "3_7d": qs.filter(created_at__lt=now - timedelta(days=3), created_at__gte=now - timedelta(days=7)).count(),
        "7d_plus": qs.filter(created_at__lt=now - timedelta(days=7)).count(),
    }


def _coverage(qs) -> dict:
    total = qs.count()
    linked = qs.exclude(Q(user_id__isnull=True) | Q(user_id="")).count()
    unlinked = total - linked
    return {"linked": linked, "unlinked": unlinked, "rate": ratio_str(linked, total), "total": total}


def _contract(filters: dict) -> dict:
    return contract_payload(
        time_basis=filters["time_basis"],
        date_from=filters["date_from"],
        date_to=filters["date_to"],
        start_dt=filters["start_dt"],
        end_dt=filters["end_dt"],
    )


def _refund_qs(filters: dict):
    qs = RefundOrder.objects.filter(is_deleted=False, status=SUCCESS_REFUND_STATUS).select_related(
        "payment_order", "payment_order__merchant"
    )
    skip_date = filters["exact_lookup"]
    if not skip_date:
        qs = qs.filter(refunded_at__gte=filters["start_dt"], refunded_at__lt=filters["end_dt"])
    order_ids = order_queryset(filters).values("id")
    if filters["merchant_id"] or filters["agent_id"] or filters["bank_code"] or filters["from_currency"] or filters["to_currency"] or filters["user_id"] or filters["exact_lookup"]:
        qs = qs.filter(payment_order_id__in=order_ids)
    return qs


def summary(filters: dict) -> dict:
    orders = order_queryset(filters)
    received = orders.filter(pay_received_at__isnull=False).filter(
        status__in=CONFIRMED_COLLECTION_STATUSES
    )
    if filters["time_basis"] == TIME_BASIS_RECEIVED:
        received = received
    elif not filters["exact_lookup"]:
        received = orders.filter(
            pay_received_at__gte=filters["start_dt"],
            pay_received_at__lt=filters["end_dt"],
        )
    refunds = _refund_qs(filters)
    refund_rows = (
        refunds.values("payment_order__from_currency")
        .annotate(
            count=Count("id"),
            amount=Coalesce(Sum("refund_amount"), Value(Decimal("0.00"))),
        )
        .order_by("payment_order__from_currency")
    )

    pending_base = PaymentOrder.objects.filter(is_deleted=False)
    if filters["merchant_id"]:
        pending_base = pending_base.filter(merchant_id=filters["merchant_id"])
    if filters["agent_id"]:
        pending_base = pending_base.filter(merchant__agent_id=filters["agent_id"])

    review_qs = pending_base.filter(status__in=PENDING_REVIEW_STATUSES)
    pay_qs = pending_base.filter(status__in=PENDING_PAY_STATUSES)
    settle_qs = pending_base.filter(status__in=PENDING_SETTLE_STATUSES)

    fee_qs = FeeShare.objects.filter(is_deleted=False, payment_order__in=orders)
    fee_rows = (
        fee_qs.values("payment_order__from_currency")
        .annotate(
            count=Count("id"),
            channel_fee=Coalesce(Sum("channel_fee"), Value(Decimal("0.00"))),
            platform_fee=Coalesce(Sum("platform_fee"), Value(Decimal("0.00"))),
            agent_fee=Coalesce(Sum("agent_fee"), Value(Decimal("0.00"))),
            total_fee=Coalesce(Sum("total_fee"), Value(Decimal("0.00"))),
        )
        .order_by("payment_order__from_currency")
    )

    return {
        "contract": _contract(filters),
        "application": {
            "label": "Applications",
            "count": orders.count(),
            "by_currency": _group_currency(orders),
        },
        "confirmed_collection": {
            "label": "System-confirmed collection",
            "evidence_level": "SYSTEM_CONFIRMED",
            "count": received.count(),
            "by_currency": _group_currency(received),
        },
        "successful_refunds": {
            "label": "Successful refunds",
            "count": refunds.count(),
            "by_currency": [
                {
                    "currency": row["payment_order__from_currency"] or "",
                    "count": row["count"],
                    "amount": money_str(row["amount"]),
                    "fee_amount": "0.00",
                }
                for row in refund_rows
            ],
        },
        "pending": {
            "review": {"count": review_qs.count(), "aging": _aging(review_qs)},
            "pay": {"count": pay_qs.count(), "aging": _aging(pay_qs)},
            "settle": {"count": settle_qs.count(), "aging": _aging(settle_qs)},
        },
        "fee_share_estimated": {
            "label": "Estimated fee share (not booked revenue)",
            "by_currency": [
                {
                    "currency": row["payment_order__from_currency"] or "",
                    "count": row["count"],
                    "channel_fee": money_str(row["channel_fee"]),
                    "platform_fee": money_str(row["platform_fee"]),
                    "agent_fee": money_str(row["agent_fee"]),
                    "total_fee": money_str(row["total_fee"]),
                }
                for row in fee_rows
            ],
        },
        "coverage": {"user_id": _coverage(orders)},
        "funnel": _funnel(orders),
    }


def _funnel(orders) -> list[dict]:
    total = orders.count()
    steps = [
        ("applied", "Application", total),
        ("pending_pay", "Awaiting funds", orders.filter(status__in=PENDING_PAY_STATUSES).count()),
        ("received", "System-confirmed collection", orders.filter(pay_received_at__isnull=False).count()),
        ("pending_settle", "Payout in progress", orders.filter(status__in=PENDING_SETTLE_STATUSES).count()),
        ("settled", "Completed", orders.filter(status__in=[
            PaymentOrder.OrderStatus.SETTLED,
            PaymentOrder.OrderStatus.COMPLETED,
        ]).count()),
    ]
    return [{"code": code, "label": label, "count": count} for code, label, count in steps]


def trend(filters: dict) -> dict:
    orders = order_queryset(filters)
    received = PaymentOrder.objects.filter(is_deleted=False, pay_received_at__isnull=False)
    received = _apply_common_filters(
        received,
        {**filters, "time_basis": TIME_BASIS_RECEIVED},
        skip_date=filters["exact_lookup"],
    )
    if not filters["exact_lookup"]:
        received = received.filter(
            pay_received_at__gte=filters["start_dt"],
            pay_received_at__lt=filters["end_dt"],
        )
    refunds = _refund_qs(filters)
    tzinfo = get_current_timezone()

    app_rows = (
        orders.annotate(day=TruncDate("created_at", tzinfo=tzinfo))
        .values("day", "from_currency")
        .annotate(
            count=Count("id"),
            amount=Coalesce(Sum("amount"), Value(Decimal("0.00"))),
        )
    )
    recv_rows = (
        received.annotate(day=TruncDate("pay_received_at", tzinfo=tzinfo))
        .values("day", "from_currency")
        .annotate(
            count=Count("id"),
            amount=Coalesce(Sum("amount"), Value(Decimal("0.00"))),
        )
    )
    refund_rows = (
        refunds.annotate(day=TruncDate("refunded_at", tzinfo=tzinfo))
        .values("day", "payment_order__from_currency")
        .annotate(
            count=Count("id"),
            amount=Coalesce(Sum("refund_amount"), Value(Decimal("0.00"))),
        )
    )

    by_day: dict[str, dict] = {}
    day = filters["date_from"]
    while day <= filters["date_to"]:
        key = day.isoformat()
        by_day[key] = {
            "date": key,
            "application_count": 0,
            "confirmed_count": 0,
            "refund_count": 0,
            "by_currency": {},
        }
        day += timedelta(days=1)

    def _bucket(day_value, currency):
        key = day_value.isoformat() if hasattr(day_value, "isoformat") else str(day_value)
        if key not in by_day:
            return None
        currencies = by_day[key]["by_currency"]
        return currencies.setdefault(
            currency or "",
            {
                "currency": currency or "",
                "application_amount": "0.00",
                "application_count": 0,
                "confirmed_amount": "0.00",
                "confirmed_count": 0,
                "refund_amount": "0.00",
                "refund_count": 0,
            },
        )

    for row in app_rows:
        if not row["day"]:
            continue
        bucket = _bucket(row["day"], row["from_currency"])
        if not bucket:
            continue
        bucket["application_count"] = row["count"]
        bucket["application_amount"] = money_str(row["amount"])
        by_day[row["day"].isoformat()]["application_count"] += row["count"]

    for row in recv_rows:
        if not row["day"]:
            continue
        bucket = _bucket(row["day"], row["from_currency"])
        if not bucket:
            continue
        bucket["confirmed_count"] = row["count"]
        bucket["confirmed_amount"] = money_str(row["amount"])
        by_day[row["day"].isoformat()]["confirmed_count"] += row["count"]

    for row in refund_rows:
        if not row["day"]:
            continue
        bucket = _bucket(row["day"], row["payment_order__from_currency"])
        if not bucket:
            continue
        bucket["refund_count"] = row["count"]
        bucket["refund_amount"] = money_str(row["amount"])
        by_day[row["day"].isoformat()]["refund_count"] += row["count"]

    series = []
    for key in sorted(by_day):
        item = by_day[key]
        item["by_currency"] = [item["by_currency"][c] for c in sorted(item["by_currency"])]
        series.append(item)
    return {"contract": _contract(filters), "series": series}


def breakdowns(filters: dict) -> dict:
    orders = order_queryset(filters)
    dimension = filters["dimension"]
    coverage = _coverage(orders)

    if dimension == "merchant":
        grouped = orders.values("merchant_id", "merchant__merchant_name", "merchant__merchant_no", "from_currency")
        key_fields = ("merchant_id", "merchant__merchant_name", "merchant__merchant_no")
    elif dimension == "user":
        grouped = orders.annotate(
            user_key=Coalesce(NullIf("user_id", Value("")), Value(UNLINKED_USER_KEY))
        ).values("user_key", "from_currency")
        key_fields = ("user_key",)
    elif dimension == "agent":
        grouped = orders.values("merchant__agent_id", "merchant__agent__agent_name", "from_currency")
        key_fields = ("merchant__agent_id", "merchant__agent__agent_name")
    elif dimension == "channel":
        grouped = orders.values("bank_code", "from_currency")
        key_fields = ("bank_code",)
    elif dimension == "status":
        grouped = orders.values("status", "from_currency")
        key_fields = ("status",)
    else:
        grouped = orders.values("from_currency")
        key_fields = ("from_currency",)

    grouped = grouped.annotate(
        count=Count("id"),
        amount=Coalesce(Sum("amount"), Value(Decimal("0.00"))),
        fee_amount=Coalesce(Sum("fee_amount"), Value(Decimal("0.00"))),
    )

    buckets: dict = {}
    for row in grouped:
        ident = tuple(row.get(f) for f in key_fields)
        item = buckets.setdefault(
            ident,
            {"key": "", "label": "", "count": 0, "unlinked": False, "by_currency": []},
        )
        if dimension == "merchant":
            item["key"] = str(row["merchant_id"] or "")
            item["label"] = row["merchant__merchant_name"] or row["merchant__merchant_no"] or ""
        elif dimension == "user":
            key = row["user_key"]
            item["key"] = key
            item["unlinked"] = key == UNLINKED_USER_KEY
            item["label"] = UNLINKED_USER_LABEL if item["unlinked"] else key
        elif dimension == "agent":
            item["key"] = str(row["merchant__agent_id"] or "")
            item["label"] = row["merchant__agent__agent_name"] or "No agent"
            item["unlinked"] = not row["merchant__agent_id"]
        elif dimension == "channel":
            item["key"] = row["bank_code"] or ""
            item["label"] = row["bank_code"] or "Unspecified channel"
            item["unlinked"] = not row["bank_code"]
        elif dimension == "status":
            item["key"] = row["status"]
            item["label"] = row["status"]
        else:
            item["key"] = row["from_currency"] or ""
            item["label"] = row["from_currency"] or "Unknown currency"
        item["count"] += row["count"]
        item["by_currency"].append(
            {
                "currency": row["from_currency"] or "",
                "count": row["count"],
                "amount": money_str(row["amount"]),
                "fee_amount": money_str(row["fee_amount"]),
            }
        )

    rows = sorted(buckets.values(), key=lambda r: r["count"], reverse=True)
    return {
        "contract": _contract(filters),
        "dimension": dimension,
        "coverage": coverage,
        "rows": rows,
    }


def serialize_order(order: PaymentOrder) -> dict:
    agent = getattr(order.merchant, "agent", None) if order.merchant_id else None
    return {
        "order_no": order.order_no,
        "merchant_order_no": order.merchant_order_no or "",
        "prn_code": order.prn_code or "",
        "unique_identification_no": order.unique_identification_no or "",
        "merchant_id": str(order.merchant_id) if order.merchant_id else "",
        "merchant_name": order.merchant.merchant_name if order.merchant else "",
        "agent_id": str(agent.id) if agent else "",
        "agent_name": agent.agent_name if agent else "",
        "user_id": order.user_id or "",
        "user_linked": bool(order.user_id),
        "status": order.status,
        "pay_method": order.pay_method,
        "bank_code": order.bank_code or "",
        "from_currency": order.from_currency or "",
        "to_currency": order.to_currency or "",
        "amount": money_str(order.amount),
        "fee_amount": money_str(order.fee_amount),
        "settle_amount": money_str(order.settle_amount),
        "beneficiary_name": order.beneficiary_name or "",
        "beneficiary_account": mask_account(order.beneficiary_account),
        "beneficiary_bank": order.beneficiary_bank or "",
        "created_at": order.created_at.isoformat() if order.created_at else "",
        "pay_received_at": order.pay_received_at.isoformat() if order.pay_received_at else "",
        "settled_at": order.settled_at.isoformat() if order.settled_at else "",
    }


def transactions(filters: dict) -> dict:
    qs = order_queryset(filters).order_by("-created_at", "-id")
    total = qs.count()
    page = filters["page"]
    page_size = filters["page_size"]
    offset = (page - 1) * page_size
    rows = list(qs[offset:offset + page_size])
    page_totals = _group_currency(qs)
    return {
        "contract": _contract(filters),
        "count": total,
        "page": page,
        "page_size": page_size,
        "results": [serialize_order(o) for o in rows],
        "page_totals": {"by_currency": page_totals},
    }


def export_rows(filters: dict) -> tuple[list[str], list[list], int]:
    qs = order_queryset(filters).order_by("-created_at", "-id")
    limit = max_export_rows()
    orders = list(qs[:limit])
    headers = [
        "order_no", "merchant_order_no", "prn_code", "merchant_name", "agent_name",
        "user_id", "status", "from_currency", "to_currency", "amount", "fee_amount",
        "settle_amount", "beneficiary_name", "beneficiary_account", "bank_code",
        "created_at", "pay_received_at", "settled_at",
    ]
    rows = []
    for order in orders:
        data = serialize_order(order)
        rows.append([excel_safe(data.get(h, "")) for h in headers])
    return headers, rows, len(orders)


def _step(code: str, title: str, at, *, verified: bool, detail: dict | None = None) -> dict:
    return {
        "code": code,
        "title": title,
        "at": at.isoformat() if hasattr(at, "isoformat") else (at or ""),
        "verified": verified,
        "evidence": "BANK_CONFIRMED" if verified else "UNVERIFIED",
        "detail": detail or {},
    }


def trace_order(order_no: str) -> dict:
    order = (
        PaymentOrder.objects.filter(order_no=order_no, is_deleted=False)
        .select_related("merchant", "merchant__agent", "quote")
        .first()
    )
    if not order:
        raise FundTraceNotFound("No matching orders found.")

    base = trace_fund(order_no=order.order_no)
    quote = None
    if order.quote_id:
        q = order.quote
        quote = {
            "quote_no": q.quote_no,
            "from_currency": q.from_currency,
            "to_currency": q.to_currency,
            "amount": money_str(q.amount),
            "fee_amount": money_str(q.fee_amount),
            "settle_amount": money_str(q.settle_amount),
            "exchange_rate": str(q.exchange_rate or ""),
            "status": q.status,
        }

    routing = list(
        RoutingLog.objects.filter(order_no=order.order_no).values(
            "created_at", "result", "currency", "amount", "error_message",
            "channel__bank_name",
        )[:20]
    )
    for item in routing:
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        item["amount"] = money_str(item.get("amount"))

    ledger = [
        {
            "entry_type": e.entry_type,
            "amount": money_str(e.amount),
            "currency": e.virtual_account.currency if e.virtual_account_id else "",
            "source_type": e.source_type,
            "remark": e.remark,
            "created_at": e.created_at.isoformat() if e.created_at else "",
            "va_number": e.virtual_account.va_number if e.virtual_account_id else "",
        }
        for e in VaLedgerEntry.objects.filter(order=order).select_related("virtual_account")[:50]
    ]
    details = list(SettlementDetail.objects.filter(payment_order=order).select_related("batch"))
    settlements = []
    for d in details:
        settlements.append({
            "batch_no": d.batch.batch_no,
            "batch_status": d.batch.status,
            "bank_txn_id": getattr(d.batch, "bank_txn_id", "") or "",
            "currency": getattr(d.batch, "currency", "") or order.from_currency,
            "amount": money_str(d.amount),
            "settle_amount": money_str(d.settle_amount),
            "settle_date": str(d.batch.settle_date),
            "verified": d.batch.status == "SETTLED" and bool(getattr(d.batch, "bank_txn_id", "")),
        })
    fee_shares = [
        {
            "channel_fee": money_str(fs.channel_fee),
            "platform_fee": money_str(fs.platform_fee),
            "agent_fee": money_str(fs.agent_fee),
            "total_fee": money_str(fs.total_fee),
            "estimated": True,
        }
        for fs in FeeShare.objects.filter(payment_order=order, is_deleted=False)
    ]
    refunds = [
        {
            "refund_no": r.refund_no,
            "status": r.status,
            "refund_amount": money_str(r.refund_amount),
            "bank_refund_id": r.bank_refund_id or "",
            "refunded_at": r.refunded_at.isoformat() if r.refunded_at else "",
            "verified": r.status == SUCCESS_REFUND_STATUS and bool(r.bank_refund_id),
        }
        for r in order.refunds.filter(is_deleted=False)
    ]
    diffs = list(
        ReconciliationDiff.objects.filter(order_no=order.order_no, is_deleted=False).values(
            "diff_type", "resolution", "amount_bank", "amount_platform", "bank_txn_id", "created_at"
        )[:20]
    )
    for item in diffs:
        item["amount_bank"] = money_str(item.get("amount_bank") or 0)
        item["amount_platform"] = money_str(item.get("amount_platform") or 0)
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()

    movements = [
        {
            "movement_no": m.movement_no,
            "movement_type": m.movement_type,
            "status": m.status,
            "evidence_level": m.evidence_level,
            "amount": money_str(m.amount),
            "currency": m.currency,
            "bank_txn_id": m.bank_txn_id,
            "from_account": mask_account(m.from_account),
            "to_account": mask_account(m.to_account),
            "occurred_at": m.occurred_at.isoformat() if m.occurred_at else "",
            "remark": m.remark,
        }
        for m in MoneyMovement.objects.filter(payment_order=order)
    ]

    payout_ok = any(
        m["movement_type"] == MoneyMovement.MovementType.SETTLEMENT_PAYOUT
        and m["status"] == MoneyMovement.MovementStatus.SUCCESS
        and m["evidence_level"] == MoneyMovement.EvidenceLevel.BANK_CONFIRMED
        for m in movements
    )
    collection_ok = bool(order.pay_received_at)
    timeline = [
        _step("quote", "Quotation bound", getattr(order.quote, "created_at", None) if order.quote_id else None, verified=bool(order.quote_id)),
        _step("applied", "Instruction submitted", order.created_at, verified=True, detail={"status": order.status}),
    ]
    agent_status = getattr(order, "agent_review_status", "") or ""
    if order.status == "PENDING_AGENT_REVIEW" or agent_status in ("pending", "approved", "rejected"):
        timeline.append(_step(
            "agent_review",
            "Agent review",
            order.agent_reviewed_at,
            verified=bool(order.agent_reviewed_at),
            detail={"status": agent_status},
        ))
    timeline.extend([
        _step("reviewed", "Operations review", order.reviewed_at, verified=bool(order.reviewed_at)),
        _step(
            "collection",
            "System-confirmed collection",
            order.pay_received_at,
            verified=collection_ok,
            detail={"bank_txn_id": order.bank_txn_id or "", "note": "System confirmation does not constitute bank-funds evidence" if collection_ok and not order.bank_txn_id else ""},
        ),
        _step(
            "payout",
            "Correspondent payout",
            order.settled_at,
            verified=payout_ok,
            detail={"note": None if payout_ok else "Unverified: no successful bank evidence"},
        ),
    ])
    va = resolve_collection_va(order)
    base["order"]["beneficiary_account"] = mask_account(base["order"].get("beneficiary_account"))
    base["quote"] = quote
    base["routing"] = routing
    base["ledger"] = ledger
    base["settlements"] = settlements
    base["fee_shares"] = fee_shares
    base["refunds"] = refunds
    base["recon_diffs"] = diffs
    base["money_movements"] = movements
    base["timeline"] = timeline
    base["virtual_account"] = base["order"].get("virtual_account")
    if va and not base["order"].get("virtual_account"):
        base["order"]["virtual_account"] = {"va_number": va.va_number, "currency": va.currency}
    return base
