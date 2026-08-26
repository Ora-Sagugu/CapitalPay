"""清算引擎 — 分账计算。

功能清单对应:
    - 手续费分润管理

分润公式:
    channel_fee = amount * channel_rate
    platform_gross = total_fee - channel_fee
    agent_fee = platform_gross * commission_rate  (如果商户有代理商)
    platform_fee = platform_gross - agent_fee  (平台净收益)
"""
from decimal import Decimal
from typing import Optional

from apps.agent.models import AgentMerchant
from apps.routing.models import BankChannel

from ..models import FeeShare


class SettlementCalculator:
    """清算计算器 — 手续费分润 & 分账计算。"""

    DEFAULT_CHANNEL_RATE = Decimal("0.003")  # 默认 0.3% 渠道费率

    def calculate_fee_share(
        self,
        payment_order,
        channel_rate: Optional[Decimal] = None,
    ) -> FeeShare:
        """计算单笔汇款的手续费分润。

        Args:
            payment_order: PaymentOrder 实例
            channel_rate: 渠道手续费率，不传则使用默认值

        Returns:
            FeeShare 记录（含全部冗余展示字段）
        """
        if channel_rate is None:
            channel_rate = self.DEFAULT_CHANNEL_RATE

        amount = payment_order.amount
        total_fee = payment_order.fee_amount
        merchant = payment_order.merchant

        # 1. 渠道手续费 = 订单金额 * 渠道费率
        channel_fee = amount * channel_rate

        # 2. 平台毛利 = 商户手续费 - 渠道手续费
        platform_gross = max(total_fee - channel_fee, Decimal("0"))

        # 3. 代理商佣金 — 优先从 merchant.agent 读取
        agent = merchant.agent if hasattr(merchant, 'agent') else None
        commission_rate = Decimal("0")
        if agent:
            # AgentMerchant 级费率优先于 Agent 级
            try:
                am = AgentMerchant.objects.filter(
                    agent=agent, merchant=merchant, is_deleted=False
                ).first()
                if am:
                    commission_rate = am.commission_rate if am.commission_rate > 0 else agent.commission_rate
                else:
                    commission_rate = agent.commission_rate
            except Exception:
                commission_rate = agent.commission_rate

        agent_fee_val = platform_gross * commission_rate

        # 4. 平台净收益 = 平台毛利 - 代理商佣金
        platform_fee_val = platform_gross - agent_fee_val

        # 获取银行通道名称
        bank_channel_name = self._resolve_bank_channel(payment_order)

        fee_share = FeeShare.objects.create(
            payment_order=payment_order,
            agent=agent,
            order_no=payment_order.order_no,
            merchant_name=merchant.merchant_name,
            agent_name=agent.agent_name if agent else "",
            bank_channel_name=bank_channel_name,
            amount=amount,
            total_fee=total_fee,
            channel_fee=channel_fee,
            platform_fee=platform_fee_val,
            agent_fee=agent_fee_val,
        )
        return fee_share

    @staticmethod
    def _resolve_bank_channel(payment_order):
        """尝试从支付订单中解析银行渠道名称。"""
        bank_code = getattr(payment_order, "bank_code", "") or ""
        if bank_code:
            ch = BankChannel.objects.filter(
                bank_code=bank_code
            ).first()
            if ch:
                return ch.bank_name or ch.bank_code

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
