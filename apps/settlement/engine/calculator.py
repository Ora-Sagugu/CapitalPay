"""清算引擎 — 分账计算。

功能清单对应:
    - 手续费分润管理

分润公式:
    channel_fee / Bank Fee = 银行 Fee Rule 算出的费用（从 Remittance Fee 中扣）
    Bank Fee 必须严格小于 Remittance Fee
    net_profit = remittance_fee - channel_fee
    agent_fee = max(net_profit, 0) * Agent Fee Share
    platform_fee = net_profit - agent_fee
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.conf import settings

from apps.core.exceptions import BusinessException, ErrorCode
from apps.routing.models import BankChannel
from apps.routing.services import RoutingService

from ..models import FeeShare

MONEY = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


class SettlementCalculator:
    """清算计算器 — 手续费分润 & 分账计算。"""

    def calculate_fee_share(
        self,
        payment_order,
        channel_rate: Optional[Decimal] = None,
    ) -> FeeShare:
        """计算或更新单笔汇款的手续费分润。"""
        banking_on = getattr(settings, "ENABLE_BANKING", True)
        agent = self._resolve_sharing_agent(payment_order)

        amount = _money(Decimal(str(payment_order.amount or 0)))
        total_fee = _money(Decimal(str(payment_order.fee_amount or 0)))
        channel = self._lookup_bank_channel(payment_order) if banking_on else None
        payout_amount = RoutingService.payout_amount_for_order(payment_order)

        splits = [leg for leg in (getattr(payment_order, "payout_splits", None) or []) if leg]
        if not banking_on:
            channel_fee = Decimal("0.00")
        elif channel_rate is not None:
            # Explicit override (tests / callers): rate only, no min/max clamp.
            channel_fee = _money(amount * Decimal(str(channel_rate or 0)))
        elif len(splits) >= 2:
            channel_fee = RoutingService.channel_fee_for_order(payment_order, payout_amount)
        elif channel is not None:
            channel_fee = RoutingService._channel_fee(channel, payout_amount)
        else:
            channel_fee = Decimal("0.00")

        if channel_fee > 0 and channel_fee >= total_fee:
            raise BusinessException(
                ErrorCode.PAYOUT_BANK_FEE_EXCEEDS,
                "Bank Fee must be less than Remittance Fee",
                400,
            )

        net_profit = _money(total_fee - channel_fee)
        shareable = net_profit if net_profit > 0 else Decimal("0.00")
        rate = Decimal("0")
        if agent is not None:
            rate = Decimal(str(agent.commission_rate or 0))
            if rate < 0:
                rate = Decimal("0")
            elif rate > 1:
                rate = Decimal("1")
        agent_fee_val = _money(shareable * rate)
        if agent_fee_val > shareable:
            agent_fee_val = shareable
        platform_fee_val = _money(net_profit - agent_fee_val)

        merchant_name = payment_order.party_name
        agent_name = agent.agent_name if agent else ""

        bank_channel_name = ""
        if banking_on:
            if len(splits) >= 2:
                bank_channel_name = RoutingService.payout_bank_names_for_order(payment_order)
            elif channel is not None:
                bank_channel_name = channel.bank_name
            if not bank_channel_name:
                bank_channel_name = self._resolve_bank_channel(payment_order)

        fee_share, _created = FeeShare.objects.update_or_create(
            payment_order=payment_order,
            defaults={
                "agent": agent,
                "order_no": payment_order.order_no,
                "merchant_name": merchant_name,
                "agent_name": agent_name,
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
            .select_related(
                "payment_order",
                "payment_order__merchant",
                "payment_order__merchant__agent",
                "payment_order__agent",
            )
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
    def _resolve_sharing_agent(payment_order):
        agent = getattr(payment_order, "agent", None)
        if agent is not None:
            return agent
        merchant = getattr(payment_order, "merchant", None)
        if merchant is None:
            return None
        return getattr(merchant, "agent", None)

    @staticmethod
    def _lookup_bank_channel(payment_order):
        bank_code = getattr(payment_order, "bank_code", "") or ""
        if not bank_code:
            return None
        return BankChannel.objects.filter(bank_code=bank_code).first()

    @classmethod
    def _resolve_bank_channel(cls, payment_order):
        """尝试从支付订单中解析银行渠道名称。"""
        ch = cls._lookup_bank_channel(payment_order)
        if ch:
            return ch.bank_name

        bank_code = getattr(payment_order, "bank_code", "") or ""
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
