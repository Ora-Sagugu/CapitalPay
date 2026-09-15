"""汇款款项追踪 — 按关键字检索并组装资金去向载荷。"""
from django.db.models import Q

from apps.account.models import VirtualAccount
from apps.payment.models import PaymentOrder

NEXT_HOP_BY_STATUS = {
    "PRE_CREATE": ("awaiting_collection", "collection_va"),
    "PENDING_AGENT_REVIEW": ("awaiting_agent_review", "agent_review"),
    "PENDING_REVIEW": ("awaiting_review", "review"),
    "PROCESSING": ("awaiting_collection", "collection_va"),
    "PENDING_PAY": ("awaiting_collection", "collection_va"),
    "PAY_RECEIVED": ("route_channel", "channel"),
    "PENDING_SETTLE": ("clearing", "clearing"),
    "SETTLED": ("delivered_beneficiary", "beneficiary"),
    "COMPLETED": ("delivered_beneficiary", "beneficiary"),
    "CLOSED": ("closed", "beneficiary"),
    "REFUNDING": ("refunding", "beneficiary"),
    "REFUNDED": ("refunded", "beneficiary"),
}

AWAITING_AGENT_PAYOUT_HOP = ("awaiting_agent_payout_request", "agent_payout_request")


def resolve_next_hop(order: PaymentOrder) -> tuple[str, str]:
    if (
        order.status == PaymentOrder.OrderStatus.PAY_RECEIVED
        and getattr(order, "agent_payout_request_status", "")
        == PaymentOrder.AgentPayoutRequestStatus.PENDING
    ):
        return AWAITING_AGENT_PAYOUT_HOP
    return NEXT_HOP_BY_STATUS.get(order.status, ("awaiting_collection", "collection_va"))


class FundTraceNotFound(Exception):
    """无匹配订单。"""


def _or_keyword(term: str) -> Q:
    return (
        Q(order_no__icontains=term)
        | Q(merchant_order_no__icontains=term)
        | Q(prn_code__icontains=term)
        | Q(beneficiary_name__icontains=term)
        | Q(merchant__merchant_name__icontains=term)
    )


def _collect_terms(*values: str) -> list[str]:
    terms = []
    for value in values:
        term = (value or "").strip()
        if term and term not in terms:
            terms.append(term)
    return terms


def _search_queryset(
    *,
    q: str = "",
    order_no: str = "",
    merchant_order_no: str = "",
    prn: str = "",
    beneficiary_name: str = "",
    remitter_name: str = "",
):
    qs = (
        PaymentOrder.objects.filter(is_deleted=False)
        .select_related("merchant")
        .prefetch_related("virtual_accounts")
        .order_by("-created_at")
    )
    terms = _collect_terms(q, order_no, merchant_order_no, prn, beneficiary_name, remitter_name)
    if not terms:
        raise FundTraceNotFound("No matching orders found.")

    combined = _or_keyword(terms[0])
    for term in terms[1:]:
        combined |= _or_keyword(term)
    return qs.filter(combined)


def resolve_collection_va(order: PaymentOrder) -> VirtualAccount | None:
    """优先订单绑定 VA，否则商户同币种启用 VAV，再退回任意启用 VA。"""
    linked = (
        order.virtual_accounts.filter(is_deleted=False)
        .select_related("master_account")
        .order_by("-va_type", "-created_at")
        .first()
    )
    if linked:
        return linked

    currency = order.currency or order.to_currency or "CNY"
    base = VirtualAccount.objects.filter(
        merchant=order.merchant,
        status=VirtualAccount.VaStatus.ACTIVE,
        is_deleted=False,
    ).select_related("master_account")
    va = base.filter(currency=currency, va_type=VirtualAccount.VaType.VAV).first()
    if va:
        return va
    va = base.filter(va_type=VirtualAccount.VaType.VAV).first()
    if va:
        return va
    return base.first()


def _serialize_va(va: VirtualAccount | None) -> dict | None:
    if not va:
        return None
    master = va.master_account
    return {
        "va_number": va.va_number,
        "va_type": va.va_type,
        "label": va.label or "",
        "bank_code": va.bank_code or "",
        "bank_name": va.bank_name or "",
        "account_holder": va.account_holder or "",
        "currency": va.currency,
        "ledger_balance": str(va.ledger_balance),
        "available_balance": str(va.available_balance),
        "status": va.status,
        "routing_code": va.routing_code or "",
        "master_account_no": master.account_no if master else "",
        "master_balance": str(master.balance) if master else "0",
        "master_bank_code": master.bank_code if master else "",
        "master_bank_name": master.bank_name if master else "",
    }


def _serialize_match(order: PaymentOrder) -> dict:
    return {
        "order_no": order.order_no,
        "merchant_order_no": order.merchant_order_no or "",
        "beneficiary_name": order.beneficiary_name or "",
        "beneficiary_bank": order.beneficiary_bank or "",
        "amount": str(order.amount),
        "from_currency": order.from_currency,
        "to_currency": order.to_currency,
        "status": order.status,
    }


def _serialize_order(order: PaymentOrder) -> dict:
    hop_code, hop_target = resolve_next_hop(order)
    created = order.created_at.strftime("%Y-%m-%d %H:%M:%S") if order.created_at else ""
    updated = order.updated_at.strftime("%Y-%m-%d %H:%M:%S") if order.updated_at else ""
    return {
        "order_no": order.order_no,
        "merchant_order_no": order.merchant_order_no or "",
        "remitter_name": (order.merchant.merchant_name if order.merchant else "") or "",
        "from_currency": order.from_currency,
        "to_currency": order.to_currency,
        "amount": str(order.amount),
        "fee_amount": str(order.fee_amount),
        "settle_amount": str(order.settle_amount),
        "fee_bearing": order.fee_bearing or "",
        "status": order.status,
        "created_at": created,
        "updated_at": updated,
        "beneficiary_name": order.beneficiary_name or "",
        "beneficiary_account": order.beneficiary_account or "",
        "beneficiary_bank": order.beneficiary_bank or "",
        "beneficiary_swift": order.beneficiary_swift or "",
        "beneficiary_address": order.beneficiary_address or "",
        "prn": order.prn_code or "",
        "next_hop": {"code": hop_code, "target": hop_target},
        "virtual_account": _serialize_va(resolve_collection_va(order)),
    }


def trace_fund(
    *,
    q: str = "",
    order_no: str = "",
    merchant_order_no: str = "",
    prn: str = "",
    beneficiary_name: str = "",
    remitter_name: str = "",
    selected_order_no: str = "",
) -> dict:
    """检索匹配订单并返回列表 + 当前展开单。"""
    qs = _search_queryset(
        q=q.strip(),
        order_no=order_no.strip(),
        merchant_order_no=merchant_order_no.strip(),
        prn=prn.strip(),
        beneficiary_name=beneficiary_name.strip(),
        remitter_name=remitter_name.strip(),
    )
    selected_order_no = (selected_order_no or "").strip()
    matches = list(qs[:50])
    if not matches:
        raise FundTraceNotFound("No matching orders found.")

    selected = next((o for o in matches if o.order_no == selected_order_no), None)
    order = selected or matches[0]

    return {
        "match_count": qs.count(),
        "matches": [_serialize_match(o) for o in matches],
        "order": _serialize_order(order),
    }
