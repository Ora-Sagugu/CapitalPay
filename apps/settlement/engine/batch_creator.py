"""清算引擎 — 批次创建。"""
from datetime import date
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from apps.payment.models import PaymentOrder
from apps.merchant.models import Merchant
from apps.merchant.services import MerchantService
from apps.core.utils import generate_batch_no
from ..models import SettlementBatch, SettlementDetail


class SettlementBatchCreator:
    """清算批次创建器。

    功能清单对应:
        - 清算批次创建
        - 商户清算批次创建
    """

    def __init__(self):
        self.merchant_service = MerchantService()

    @transaction.atomic
    def create_daily_batches(self, settle_date: date) -> list[SettlementBatch]:
        """为所有有交易的商户创建日清算批次。

        从待清算订单 (PENDING_SETTLE) 中按商户分组，生成清算批次。
        """
        pending = PaymentOrder.objects.filter(
            status=PaymentOrder.OrderStatus.PENDING_SETTLE,
            pay_received_at__date=settle_date,
            is_deleted=False,
        ).select_related("merchant")

        if not pending.exists():
            return []

        # 按商户分组
        merchant_groups = {}
        for order in pending:
            m_id = order.merchant_id
            merchant_groups.setdefault(m_id, []).append(order)

        batches = []
        for merchant_id, orders in merchant_groups.items():
            batch = self._create_merchant_batch(merchant_id, orders, settle_date)
            batches.append(batch)

        return batches

    def _create_merchant_batch(self, merchant_id, orders: list[PaymentOrder], settle_date: date) -> SettlementBatch:
        """为单个商户创建清算批次。"""
        merchant = orders[0].merchant

        total_amount = sum(o.amount for o in orders)
        total_fee = sum(o.fee_amount for o in orders)
        settle_net = sum(o.settle_amount for o in orders)

        # 获取结算账户信息
        settle_account = self.merchant_service.get_default_settlement_account(merchant)
        account_info = {}
        if settle_account:
            from apps.core.utils import decrypt_field
            account_info = {
                "bank_name": settle_account.bank_name,
                "account_name": settle_account.account_name,
                "account_number_masked": "****" + decrypt_field(settle_account.account_number)[-4:],
            }

        # 创建批次
        batch = SettlementBatch.objects.create(
            batch_no=generate_batch_no(),
            settle_date=settle_date,
            merchant=merchant,
            total_count=len(orders),
            total_amount=total_amount,
            fee_total=total_fee,
            settle_net_amount=settle_net,
            status=SettlementBatch.SettleStatus.PENDING,
            settlement_account_info=account_info,
        )

        # 创建清算明细
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

        # 更新订单状态: PENDING_SETTLE → SETTLED
        PaymentOrder.objects.filter(
            pk__in=[o.pk for o in orders]
        ).update(
            status=PaymentOrder.OrderStatus.SETTLED,
            settled_at=transaction.get_connection().ops.value_to_db_datetime(
                __import__("django").utils.timezone.now()
            ) if hasattr(transaction.get_connection().ops, "value_to_db_datetime") else None,
        )
        # 实际用 Django ORM 的 now():
        from django.utils import timezone
        PaymentOrder.objects.filter(pk__in=[o.pk for o in orders]).update(
            status=PaymentOrder.OrderStatus.SETTLED,
            settled_at=timezone.now(),
        )

        return batch
