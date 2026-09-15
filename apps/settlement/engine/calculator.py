"""清算引擎 — 分账计算。

功能清单对应:
    - 手续费分润管理

分润公式:
    agent_fee = fee_amount * commission_rate
    platform_fee = fee_amount - agent_fee
    channel_fee = amount * channel_rate  (银行成本，不参与代理分成)
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.conf import settings

from apps.agent.models import AgentMerchant
from apps.routing.models import BankChannel

from ..models import FeeShare

MONEY = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


class SettlementCalculator:
    """清算计算器 — 手续费分润 & 分账计算。"""

    DEFAULT_CHANNEL_RATE = Decimal("0.003")  # 默认 0.3% 渠道费率

    def calculate_fee_share(
        self,
        payment_order,
        channel_rate: Optional[Decimal] = None,
    ) -> FeeShare:
        """计算或更新单笔汇款的手续费分润。"""
        banking_on = getattr(settings, "ENABLE_BANKING", True)
        agents_on = getattr(settings, "ENABLE_AGENTS", True)

        if not banking_on:
            channel_rate = Decimal("0")
        elif channel_rate is None:
            from apps.param.services import resolve_channel_rate
            channel_rate = resolve_channel_rate(
                getattr(payment_order, "bank_code", None),
                getattr(payment_order, "pay_method", None),
            )
            if not channel_rate:
                channel_rate = self.DEFAULT_CHANNEL_RATE

        amount = _money(Decimal(str(payment_order.amount or 0)))
        total_fee = _money(Decimal(str(payment_order.fee_amount or 0)))
        channel_rate = Decimal(str(channel_rate or 0))
        merchant = payment_order.merchant

        channel_fee = _money(amount * channel_rate)

        agent = None
        commission_rate = Decimal("0")
        if agents_on:
            agent = merchant.agent if hasattr(merchant, "agent") else None
            if agent:
                try:
                    am = AgentMerchant.objects.filter(
                        agent=agent, merchant=merchant, is_deleted=False
                    ).first()
                    if am and am.commission_rate > 0:
                        commission_rate = am.commission_rate
                    else:
                        commission_rate = agent.commission_rate
                except Exception:
                    commission_rate = agent.commission_rate

        commission_rate = Decimal(str(commission_rate or 0))
        agent_fee_val = _money(total_fee * commission_rate)
        platform_fee_val = _money(total_fee - agent_fee_val)

        bank_channel_name = self._resolve_bank_channel(payment_order) if banking_on else ""

        fee_share, _created = FeeShare.objects.update_or_create(
            payment_order=payment_order,
            defaults={
                "agent": agent,
                "order_no": payment_order.order_no,
                "merchant_name": merchant.merchant_name,
                "agent_name": agent.agent_name if agent else "",
                "bank_channel_name": bank_channel_name,
                "amount": amount,
                "total_fee": total_fee,
                "channel_fee": channel_fee,
                "platform_fee": platform_fee_val,
                "agent_fee": agent_fee_val,
            },
        )
        return fee_share

    def recompute_all_fee_shares(self) -> int:
        """按当前公式重算所有已关联订单的分润。"""
        updated = 0
        qs = (
            FeeShare.objects.filter(payment_order__isnull=False, is_deleted=False)
            .select_related("payment_order", "payment_order__merchant", "payment_order__merchant__agent")
        )
        for share in qs:
            order = share.payment_order
            if not order:
                continue
            self.calculate_fee_share(order)
            updated += 1
        return updated

    def calculate_batch_share(self, batch) -> list:
        """为批次内尚未分润的订单补建 FeeShare。"""
        shares = []
        for detail in batch.details.select_related("payment_order", "payment_order__merchant"):
            order = detail.payment_order
            if not order:
                continue
            if FeeShare.objects.filter(payment_order=order).exists():
                continue
            try:
                shares.append(self.calculate_fee_share(order))
            except Exception:
                continue
        return shares

    @staticmethod
    def _resolve_bank_channel(payment_order):
        """尝试从支付订单中解析银行渠道名称。"""
        bank_code = getattr(payment_order, "bank_code", "") or ""
        if bank_code:
            ch = BankChannel.objects.filter(bank_code=bank_code).first()
            if ch:
                return ch.bank_name

            bank_txn_id = getattr(payment_order, "bank_txn_id", "") or ""
            if bank_txn_id:
                try:
                    import json
                    snapshot = json.loads(bank_txn_id)
                    name = snapshot.get("bank_name") or snapshot.get("channel_name") or ""
                    if name:
                        return name
                except (json.JSONDecodeError, TypeError):
                    pass
        return str(bank_code) if bank_code else ""
