"""PRN 生成服务 — 1 位代理前缀 + 年积日 + 当日序号，保证全局唯一。"""
import re
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import BusinessException, ErrorCode
from apps.payment.models import PaymentOrder, PRNConfig, PrnIssuance

NO_AGENT_PREFIX = "0"
PRN_TOKEN = r"[A-Za-z0-9]\d{5}"
PRN_PREFIXED_RE = re.compile(rf"(?:PRN|prn)[:：\s]*({PRN_TOKEN})")
PRN_STANDALONE_RE = re.compile(rf"(?:^|\s)({PRN_TOKEN})(?:\s|$)")


def normalize_prn_code(code: str) -> str:
    """Uppercase a letter prefix so bank remarks match stored codes."""
    value = (code or "").strip()
    if len(value) == 6 and value[0].isalpha():
        return value[0].upper() + value[1:]
    return value


def is_valid_prn_code(code: str) -> bool:
    """True when code matches prefix + day-of-year(001–366) + daily seq(01–99)."""
    value = normalize_prn_code(code)
    if len(value) != 6 or not re.fullmatch(PRN_TOKEN, value):
        return False
    doy = int(value[1:4])
    seq = int(value[4:6])
    return 1 <= doy <= 366 and 1 <= seq <= 99


def extract_prn_from_remark(remark: str) -> str | None:
    """Extract a 6-character PRN from a bank remark."""
    if not remark:
        return None
    prefixed = PRN_PREFIXED_RE.search(remark)
    if prefixed:
        code = normalize_prn_code(prefixed.group(1))
        return code if is_valid_prn_code(code) else None
    for token in PRN_STANDALONE_RE.findall(remark):
        code = normalize_prn_code(token)
        if is_valid_prn_code(code):
            return code
    return None


def _resolve_prn_prefix(*, order=None, agent=None) -> str:
    resolved = agent
    if resolved is None and order is not None:
        merchant = getattr(order, "merchant", None)
        if merchant is not None:
            resolved = getattr(merchant, "agent", None)
    if resolved is None:
        return NO_AGENT_PREFIX
    agent_no = (getattr(resolved, "agent_no", None) or "").strip()
    if not agent_no:
        return NO_AGENT_PREFIX
    first = agent_no[0]
    if first.isalpha():
        return first.upper()
    if first.isdigit():
        return first
    return NO_AGENT_PREFIX


def _occupied_sequences(base: str) -> set[int]:
    occupied: set[int] = set()
    prefixes = {base, base.upper(), base.lower()}
    codes = []
    for start in prefixes:
        codes.extend(
            PaymentOrder.objects.filter(prn_code__startswith=start).values_list("prn_code", flat=True)
        )
        codes.extend(
            PrnIssuance.objects.filter(prn_code__startswith=start).values_list("prn_code", flat=True)
        )
    for raw in codes:
        code = normalize_prn_code(str(raw or ""))
        if len(code) != 6 or not code[4:].isdigit():
            continue
        if code[:4] != base:
            continue
        occupied.add(int(code[4:]))
    return occupied


def _lock_prn_generation():
    config = PRNConfig.get_config()
    list(PRNConfig.objects.select_for_update().filter(pk=config.pk))


@transaction.atomic
def generate_prn(order=None, agent=None, config=None, on_date=None) -> str:
    """Generate a unique 6-character PRN.

    Format: prefix (agent first char or 0) + day-of-year (001-366) + daily sequence (01-99).
    ``config`` is ignored; the structured rule replaces PRNConfig random generation.
    ``on_date`` defaults to the local calendar day (useful for seed / historical rows).
    """
    _lock_prn_generation()
    prefix = _resolve_prn_prefix(order=order, agent=agent)
    day = on_date or timezone.localdate()
    doy = f"{day.timetuple().tm_yday:03d}"
    base = f"{prefix}{doy}"
    occupied = _occupied_sequences(base)
    next_seq = (max(occupied) if occupied else 0) + 1
    if next_seq > 99:
        raise BusinessException(
            "INTERNAL_ERROR",
            "PRN code generation failed, daily sequence exhausted",
        )
    return f"{base}{next_seq:02d}"


def apply_prn(
    agent,
    *,
    merchant_no: str = "",
    amount=None,
    currency: str = "CNY",
    reference: str = "",
    expire_hours: int = 72,
) -> PrnIssuance:
    """代理 HMAC 申请独立 PRN，不依赖运营审单。"""
    merchant = None
    if merchant_no:
        from apps.merchant.models import Merchant
        merchant = Merchant.objects.filter(merchant_no=merchant_no, is_deleted=False).first()
        if not merchant:
            raise BusinessException(ErrorCode.MERCHANT_NOT_FOUND, "The customer does not exist")

    amt = None
    if amount not in (None, ""):
        amt = Decimal(str(amount))
        if amt <= 0:
            raise BusinessException("AMOUNT_INVALID", "The amount must be greater than zero")

    hours = int(expire_hours or 72)
    if hours <= 0:
        hours = 72

    code = generate_prn(agent=agent)
    return PrnIssuance.objects.create(
        prn_code=code,
        agent=agent,
        merchant=merchant,
        amount=amt,
        currency=(currency or "CNY").upper(),
        reference=reference or "",
        status=PrnIssuance.Status.ISSUED,
        expires_at=timezone.now() + timedelta(hours=hours),
    )


def bind_prn_to_order(order: PaymentOrder, prn_code: str) -> str:
    """将已签发的代理 PRN 绑定到订单；失败则新生成。"""
    code = normalize_prn_code((prn_code or "").strip())
    if code and not is_valid_prn_code(code):
        code = ""
    if code:
        issuance = PrnIssuance.objects.filter(prn_code__iexact=code).first()
        if issuance:
            if issuance.status == PrnIssuance.Status.EXPIRED:
                code = ""
            elif issuance.expires_at and issuance.expires_at < timezone.now():
                issuance.status = PrnIssuance.Status.EXPIRED
                issuance.save(update_fields=["status", "updated_at"])
                code = ""
            elif issuance.status in (PrnIssuance.Status.ISSUED, PrnIssuance.Status.BOUND):
                if PaymentOrder.objects.filter(prn_code__iexact=code).exclude(pk=order.pk).exists():
                    code = ""
                else:
                    issuance.status = PrnIssuance.Status.BOUND
                    issuance.order = order
                    issuance.save(update_fields=["status", "order", "updated_at"])
                    return issuance.prn_code
            else:
                code = ""
        elif PaymentOrder.objects.filter(prn_code__iexact=code).exclude(pk=order.pk).exists():
            code = ""
        else:
            return code
    if not code:
        code = generate_prn(order=order)
    return code


def mark_prn_matched(prn_code: str, order: PaymentOrder | None = None):
    """收款确认后将签发记录标为已匹配。"""
    if not prn_code:
        return
    qs = PrnIssuance.objects.filter(
        prn_code__iexact=prn_code,
        status__in=[PrnIssuance.Status.ISSUED, PrnIssuance.Status.BOUND],
    )
    issuance = qs.first()
    if not issuance:
        return
    issuance.status = PrnIssuance.Status.MATCHED
    if order:
        issuance.order = order
        issuance.save(update_fields=["status", "order", "updated_at"])
    else:
        issuance.save(update_fields=["status", "updated_at"])
