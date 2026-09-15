"""Mock inbound bank-credit ingest and PRN matching.

Does not confirm collection on the order. Bank webhooks can call ingest_credit later.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.account.models import NostroAccount
from apps.core.exceptions import BusinessException, ErrorCode
from apps.payment.models import BankCreditNotification, PaymentOrder
from apps.payment.services.fund_trace import resolve_collection_va
from apps.payment.services.prn_service import extract_prn_from_remark, normalize_prn_code


def generate_notification_no() -> str:
    now = timezone.now()
    return f"BN{now.strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"


def generate_txn_id() -> str:
    now = timezone.now()
    return f"BNK{now.strftime('%Y%m%d%H%M%S')}{random.randint(100000, 999999)}"


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _as_decimal(value) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BusinessException(ErrorCode.ORDER_AMOUNT_MISMATCH, "A valid credit amount is required") from exc
    if amount <= 0:
        raise BusinessException(ErrorCode.ORDER_AMOUNT_MISMATCH, "The credit amount must be greater than zero")
    return amount.quantize(Decimal("0.01"))


def _as_datetime(value) -> datetime:
    if value is None or value == "":
        return timezone.now()
    if isinstance(value, datetime):
        dt = value
    else:
        dt = parse_datetime(str(value))
        if dt is None:
            raise BusinessException("PARAM_INVALID", "txn_time must be a valid datetime")
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _unique_notification_no() -> str:
    for _ in range(8):
        code = generate_notification_no()
        if not BankCreditNotification.objects.filter(notification_no=code).exists():
            return code
    return generate_notification_no()


def _unique_txn_id() -> str:
    for _ in range(8):
        code = generate_txn_id()
        if not BankCreditNotification.objects.filter(txn_id=code).exists():
            return code
    return generate_txn_id()


def _resolve_prn(prn_code: str, remark: str) -> str:
    explicit = normalize_prn_code(prn_code or "")
    if explicit:
        return explicit
    return extract_prn_from_remark(remark or "") or ""


def _find_order(prn_code: str, order_no: str = "") -> PaymentOrder | None:
    if order_no:
        order = (
            PaymentOrder.objects.filter(order_no=order_no, is_deleted=False)
            .select_related("merchant")
            .first()
        )
        if order:
            return order
    if not prn_code:
        return None
    return (
        PaymentOrder.objects.filter(prn_code__iexact=prn_code, is_deleted=False)
        .select_related("merchant")
        .first()
    )


def _fill_collection_bank(notification: BankCreditNotification, order: PaymentOrder | None) -> None:
    if notification.bank_code and notification.bank_name and notification.account_no:
        return
    if order is None:
        return
    va = resolve_collection_va(order)
    if not va:
        return
    master = va.master_account
    if not notification.bank_code:
        notification.bank_code = (va.bank_code or (master.bank_code if master else "")) or ""
    if not notification.bank_name:
        notification.bank_name = (va.bank_name or (master.bank_name if master else "")) or ""
    if not notification.account_no:
        notification.account_no = (master.account_no if master else "") or ""


def _apply_match(notification: BankCreditNotification, order: PaymentOrder | None, prn_code: str) -> None:
    notification.prn_code = prn_code or notification.prn_code or ""
    if order is None:
        notification.status = (
            BankCreditNotification.Status.UNMATCHED
            if not prn_code
            else BankCreditNotification.Status.UNMATCHED
        )
        notification.order = None
        notification.merchant = None
        notification.order_no = ""
        notification.merchant_no = ""
        notification.merchant_name = ""
        return

    merchant = order.merchant
    notification.order = order
    notification.merchant = merchant
    notification.order_no = order.order_no
    notification.merchant_no = getattr(merchant, "merchant_no", "") or ""
    notification.merchant_name = getattr(merchant, "merchant_name", "") or ""
    if not notification.prn_code:
        notification.prn_code = order.prn_code or ""
    expected = Decimal(order.amount).quantize(Decimal("0.01"))
    notification.status = (
        BankCreditNotification.Status.MATCHED
        if notification.amount == expected
        else BankCreditNotification.Status.MISMATCH
    )
    _fill_collection_bank(notification, order)


def _lookup_nostro(*, nostro_id="", bank_code="") -> NostroAccount | None:
    qs = NostroAccount.objects.filter(is_deleted=False, is_active=True)
    if nostro_id:
        return qs.filter(pk=nostro_id).first()
    if bank_code:
        return qs.filter(bank_code=bank_code).order_by("account_type", "created_at").first()
    return None


def ingest_credit(
    *,
    amount,
    currency: str,
    remark: str = "",
    prn_code: str = "",
    order_no: str = "",
    txn_id: str = "",
    txn_time=None,
    bank_code: str = "",
    bank_name: str = "",
    account_no: str = "",
    nostro_id: str = "",
    source: str = BankCreditNotification.Source.MOCK,
    raw_payload: dict | None = None,
) -> BankCreditNotification:
    """Create (or return) a bank credit notification and match PRN to an order."""
    txn_id = (txn_id or "").strip()
    if txn_id:
        existing = BankCreditNotification.objects.filter(txn_id=txn_id, is_deleted=False).first()
        if existing:
            return existing

    nostro = _lookup_nostro(nostro_id=nostro_id, bank_code=bank_code)
    if nostro:
        bank_code = bank_code or nostro.bank_code
        bank_name = bank_name or nostro.bank_name
        account_no = account_no or nostro.account_no

    credit_amount = _as_decimal(amount)
    ccy = (currency or "").strip().upper()
    if len(ccy) != 3:
        raise BusinessException("PARAM_INVALID", "A 3-letter currency code is required")

    prn = _resolve_prn(prn_code, remark)
    order = _find_order(prn, order_no)
    if not prn and order and order.prn_code:
        prn = order.prn_code
    if not remark and prn:
        remark = f"PRN:{prn}"

    with transaction.atomic():
        notification = BankCreditNotification(
            notification_no=_unique_notification_no(),
            txn_id=txn_id or _unique_txn_id(),
            txn_time=_as_datetime(txn_time),
            amount=credit_amount,
            currency=ccy,
            remark=(remark or "")[:256],
            prn_code=prn,
            bank_code=(bank_code or "")[:16],
            bank_name=(bank_name or "")[:128],
            account_no=(account_no or "")[:64],
            source=source if source in BankCreditNotification.Source.values else BankCreditNotification.Source.MOCK,
            raw_payload=_json_safe(raw_payload or {}),
            status=BankCreditNotification.Status.RECEIVED,
        )
        _apply_match(notification, order, prn)
        notification.save()
        return notification


def simulate_credit(payload: dict) -> BankCreditNotification:
    """Ops mock ingest. Same matcher as a future bank webhook."""
    order_no = (payload.get("order_no") or "").strip()
    prn_code = (payload.get("prn_code") or "").strip()
    remark = payload.get("remark") or ""
    amount = payload.get("amount")
    currency = payload.get("currency") or ""

    prn = _resolve_prn(prn_code, remark)
    order = _find_order(prn, order_no)
    if order:
        if amount in (None, ""):
            amount = order.amount
        if not currency:
            currency = order.from_currency or order.currency
        if not prn_code:
            prn_code = order.prn_code or prn

    if amount in (None, ""):
        raise BusinessException("PARAM_MISSING", "amount is required when no matching order is found")
    if not currency:
        raise BusinessException("PARAM_MISSING", "currency is required when no matching order is found")

    body = dict(payload)
    body["source"] = BankCreditNotification.Source.MOCK
    return ingest_credit(
        amount=amount,
        currency=currency,
        remark=remark,
        prn_code=prn_code,
        order_no=order_no,
        txn_id=payload.get("txn_id") or "",
        txn_time=payload.get("txn_time"),
        bank_code=payload.get("bank_code") or "",
        bank_name=payload.get("bank_name") or "",
        account_no=payload.get("account_no") or "",
        nostro_id=str(payload.get("nostro_id") or ""),
        source=BankCreditNotification.Source.MOCK,
        raw_payload=body,
    )
