"""清算引擎 — 批次创建。"""
from datetime import date
from decimal import Decimal
from django.db import transaction
from apps.payment.models import PaymentOrder
from apps.merchant.services import MerchantService
from apps.core.utils import decrypt_field, generate_batch_no
from ..models import SettlementBatch, SettlementDetail


class SettlementBatchCreator:
    """清算批次创建器。

    按商户 + 币种 + 日期从待清算订单生成批次。
    创建批次时不把订单标为 SETTLED，须等银行出款成功。
    """

    def __init__(self):
        self.merchant_service = MerchantService()

    @transaction.atomic
    def create_daily_batches(self, settle_date: date) -> list[SettlementBatch]:
        pending = PaymentOrder.objects.filter(
            status=PaymentOrder.OrderStatus.PENDING_SETTLE,
            pay_received_at__date=settle_date,
            is_deleted=False,
        ).select_related("merchant", "agent", "agent_customer")

        if not pending.exists():
            return []

        groups = {}
        for order in pending:
            if SettlementDetail.objects.filter(payment_order=order).exists():
                continue
            currency = order.from_currency or order.currency or ""
            owner_key = ("agent", order.agent_id) if order.agent_id else ("merchant", order.merchant_id)
            groups.setdefault((owner_key, currency), []).append(order)

        batches = []
        for (owner_key, currency), orders in groups.items():
            batches.append(self._create_book_batch(owner_key, orders, settle_date, currency))
        return batches

    def _create_book_batch(
        self, owner_key, orders: list[PaymentOrder], settle_date: date, currency: str
    ) -> SettlementBatch:
        owner_type, owner_id = owner_key
        merchant = orders[0].merchant if owner_type == "merchant" else None
        agent = orders[0].agent if owner_type == "agent" else None
        total_amount = sum((o.amount or Decimal("0")) for o in orders)
        total_fee = sum((o.fee_amount or Decimal("0")) for o in orders)
        settle_net = sum((o.settle_amount or Decimal("0")) for o in orders)

        account_info = {"currency": currency}
        if merchant:
            settle_account = self.merchant_service.get_default_settlement_account(merchant)
            if settle_account:
                raw_account = decrypt_field(settle_account.account_number) or ""
                account_info.update({
                    "bank_name": settle_account.bank_name,
                    "account_name": settle_account.account_name,
                    "account_no": raw_account,
                    "to_account": raw_account,
                    "account_number_masked": ("****" + raw_account[-4:]) if len(raw_account) >= 4 else "****",
                })
        elif agent:
            raw_account = agent.settlement_account_no or ""
            account_info.update({
                "bank_name": agent.settlement_bank_name or "",
                "account_name": agent.settlement_account_holder or agent.agent_name,
                "account_no": raw_account,
                "to_account": raw_account,
                "account_number_masked": ("****" + raw_account[-4:]) if len(raw_account) >= 4 else "****",
            })

        batch = SettlementBatch.objects.create(
            batch_no=generate_batch_no(),
            settle_date=settle_date,
            merchant=merchant,
            agent=agent,
            currency=currency or "",
            total_count=len(orders),
            total_amount=total_amount,
            fee_total=total_fee,
            settle_net_amount=settle_net,
            status=SettlementBatch.SettleStatus.PENDING,
            settlement_account_info=account_info,
        )
        SettlementDetail.objects.bulk_create([
            SettlementDetail(
                batch=batch,
                payment_order=order,
                order_no=order.order_no,
                amount=order.amount,
                fee=order.fee_amount,
                settle_amount=order.settle_amount,
            )
            for order in orders
        ])
        return batch
