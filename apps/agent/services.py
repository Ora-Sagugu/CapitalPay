"""Agent services"""
import datetime
import random
import secrets
import string
import uuid
from decimal import Decimal
from datetime import datetime as dt

from django.utils import timezone

from apps.account.models import NostroAccount, VirtualAccount
from apps.agent.models import Agent

AGENT_NO_ALPHABET = string.ascii_letters + string.digits
AGENT_NO_LENGTH = 8
_AGENT_NO_MAX_ATTEMPTS = 32


def generate_agent_no():
    """生成 8 位代理编码：大小写字母 + 数字，随机且唯一。"""
    for _ in range(_AGENT_NO_MAX_ATTEMPTS):
        code = "".join(secrets.choice(AGENT_NO_ALPHABET) for _ in range(AGENT_NO_LENGTH))
        if not Agent.objects.filter(agent_no=code).exists():
            return code
    raise RuntimeError("Failed to generate a unique agent code")


def generate_commission_no():
    """生成佣金单号 CM + 时间戳 + 随机数"""
    now = dt.now()
    rand_part = random.randint(10000, 99999)
    return f"CM{now.strftime('%Y%m%d%H%M%S')}{rand_part}"


def ensure_agent_api_credentials(agent: Agent) -> Agent:
    """确保代理拥有 HMAC API 凭证。"""
    changed = []
    if not agent.api_key:
        agent.api_key = f"ak_{uuid.uuid4().hex[:32]}"
        changed.append("api_key")
    if not agent.api_secret:
        agent.api_secret = f"sk_{uuid.uuid4().hex}"
        changed.append("api_secret")
    if changed:
        changed.append("updated_at")
        agent.save(update_fields=changed)
    return agent


def _create_agent_nostro(agent: Agent, account_type: str, currency: str) -> NostroAccount:
    suffix = "CUR" if account_type == NostroAccount.AccountType.CURRENT else "FEE"
    account_no = f"N{datetime.date.today().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
    return NostroAccount.objects.create(
        agent=agent,
        account_no=account_no,
        bank_name="CapitalPay Nostro",
        bank_code="NSTR",
        account_number=f"ACCT-{agent.agent_no}-{suffix}-{currency}",
        account_type=account_type,
        currency=currency,
        balance=Decimal("0"),
    )


def _ensure_agent_vla(agent: Agent, master: NostroAccount, label: str) -> VirtualAccount:
    existing = agent.virtual_accounts.filter(
        is_deleted=False, master_account=master, va_type=VirtualAccount.VaType.VLA,
    ).first()
    if existing:
        return existing
    va_number = f"VLA{datetime.date.today().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"
    return VirtualAccount.objects.create(
        master_account=master,
        agent=agent,
        va_number=va_number,
        va_type=VirtualAccount.VaType.VLA,
        label=label,
        reference=f"{agent.agent_no}-{master.account_type}-{master.currency}",
        bank_name=master.bank_name,
        bank_code=master.bank_code,
        account_holder=agent.agent_name,
        country="CN",
        currency=master.currency or "CNY",
        status=VirtualAccount.VaStatus.ACTIVE,
        opened_at=timezone.now(),
    )


def ensure_agent_accounts(agent: Agent, currency: str = "CNY") -> list[NostroAccount]:
    """KYC 通过后幂等创建代理往来账户 + 手续费账户，并各挂一条内部 VLA。"""
    created: list[NostroAccount] = []
    specs = (
        (NostroAccount.AccountType.CURRENT, f"{agent.agent_name} 往来账户"),
        (NostroAccount.AccountType.FEE, f"{agent.agent_name} 手续费账户"),
    )
    for account_type, label in specs:
        master = agent.nostro_accounts.filter(
            is_deleted=False, account_type=account_type, currency=currency,
        ).first()
        if not master:
            master = _create_agent_nostro(agent, account_type, currency)
            created.append(master)
        _ensure_agent_vla(agent, master, label)
    return created


def get_agent_account(agent: Agent, account_type: str, currency: str | None = None) -> NostroAccount | None:
    qs = agent.nostro_accounts.filter(is_deleted=False, account_type=account_type, is_active=True)
    if currency:
        match = qs.filter(currency=currency).first()
        if match:
            return match
    return qs.first()


def get_agent_ledger_va(agent: Agent, account_type: str, currency: str | None = None) -> VirtualAccount | None:
    master = get_agent_account(agent, account_type, currency)
    if not master:
        return None
    return agent.virtual_accounts.filter(
        is_deleted=False,
        master_account=master,
        va_type=VirtualAccount.VaType.VLA,
        status=VirtualAccount.VaStatus.ACTIVE,
    ).first()


def _money_str(value) -> str:
    from decimal import ROUND_HALF_UP
    n = Decimal(str(value or 0))
    return format(n.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")


def build_agent_fee_overview(agent: Agent, recent_limit: int = 20) -> dict:
    """按代理汇总交易笔数、分币种手续费与已记账提成。"""
    from django.db.models import Count, Sum
    from django.db.models.functions import Coalesce, NullIf
    from django.db.models import Value, CharField

    from apps.payment.models import PaymentOrder
    from apps.settlement.models import FeeShare

    currency_expr = Coalesce(
        NullIf("from_currency", Value("")),
        NullIf("currency", Value("")),
        Value(""),
        output_field=CharField(),
    )
    share_currency_expr = Coalesce(
        NullIf("payment_order__from_currency", Value("")),
        NullIf("payment_order__currency", Value("")),
        Value(""),
        output_field=CharField(),
    )

    orders = PaymentOrder.objects.filter(merchant__agent_id=agent.id, is_deleted=False)
    order_rows = (
        orders.annotate(ccy=currency_expr)
        .values("ccy")
        .annotate(
            order_count=Count("id"),
            volume=Coalesce(Sum("amount"), Decimal("0")),
            customer_fee=Coalesce(Sum("fee_amount"), Decimal("0")),
        )
        .order_by("ccy")
    )
    share_map = {
        row["ccy"] or "": row
        for row in (
            FeeShare.objects.filter(agent=agent, is_deleted=False)
            .annotate(ccy=share_currency_expr)
            .values("ccy")
            .annotate(agent_fee=Coalesce(Sum("agent_fee"), Decimal("0")))
        )
    }

    by_currency = []
    seen = set()
    for row in order_rows:
        ccy = row["ccy"] or ""
        seen.add(ccy)
        share = share_map.get(ccy, {})
        by_currency.append({
            "currency": ccy or "—",
            "order_count": row["order_count"],
            "volume": _money_str(row["volume"]),
            "customer_fee": _money_str(row["customer_fee"]),
            "agent_fee": _money_str(share.get("agent_fee")),
        })
    for ccy, share in share_map.items():
        if ccy in seen:
            continue
        by_currency.append({
            "currency": ccy or "—",
            "order_count": 0,
            "volume": "0.00",
            "customer_fee": "0.00",
            "agent_fee": _money_str(share.get("agent_fee")),
        })

    recent_orders = []
    for order in (
        orders.select_related("merchant")
        .prefetch_related("fee_shares")
        .order_by("-created_at")[:recent_limit]
    ):
        share = next((item for item in order.fee_shares.all() if not item.is_deleted), None)
        recent_orders.append({
            "id": str(order.id),
            "order_no": order.order_no,
            "customer_name": order.merchant.merchant_name if order.merchant else "",
            "currency": order.from_currency or order.currency,
            "amount": _money_str(order.amount),
            "fee_amount": _money_str(order.fee_amount),
            "agent_fee": _money_str(share.agent_fee if share else 0),
            "status": order.status,
            "created_at": order.created_at.isoformat() if order.created_at else None,
        })

    return {
        "id": str(agent.id),
        "agent_no": agent.agent_no,
        "agent_name": agent.agent_name,
        "status": agent.status,
        "commission_rate": format(Decimal(str(agent.commission_rate or 0)), "f"),
        "customer_count": agent.direct_merchants.filter(is_deleted=False).count(),
        "order_count": orders.count(),
        "currency_count": len(by_currency),
        "by_currency": by_currency,
        "recent_orders": recent_orders,
    }
