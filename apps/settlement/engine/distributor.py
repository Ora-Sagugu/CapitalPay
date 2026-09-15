"""清算引擎 — 资金划拨。

功能清单对应:
    - nostro账户资金调拨
    - 商户分账结算（资金划拨到商户结算账户）
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.account.models import MoneyMovement
from apps.account.money_movements import MoneyMovementService
from apps.account.services import AccountService
from apps.core.utils import decrypt_field
from apps.merchant.services import MerchantService
from apps.payment.gateway import BankGatewayRouter
from apps.payment.models import PaymentOrder
from ..models import SettlementBatch

logger = logging.getLogger(__name__)


class FundsDistributor:
    """资金划拨器 — 将净结算金额打款到商户结算账户。"""

    def __init__(self):
        self.account_service = AccountService()

    def distribute(self, batch: SettlementBatch) -> SettlementBatch:
        """执行资金划拨。订单仅在银行成功后进入 SETTLED。"""
        if batch.status != SettlementBatch.SettleStatus.PENDING:
            from apps.core.exceptions import BusinessException
            raise BusinessException("SETTLE_STATUS_INVALID", "The settlement batch is not in a status that permits disbursement")

        batch.status = SettlementBatch.SettleStatus.PROCESSING
        batch.save(update_fields=["status"])

        try:
            info = dict(batch.settlement_account_info or {})
            try:
                cfg = batch.merchant.split_config
            except Exception:
                cfg = None
            merchant_amount = batch.settle_net_amount
            if cfg and cfg.auto_split:
                merchant_amount = (batch.settle_net_amount * (cfg.merchant_ratio or Decimal("1"))).quantize(Decimal("0.01"))
                info["split"] = {
                    "merchant_ratio": str(cfg.merchant_ratio),
                    "platform_ratio": str(cfg.platform_ratio),
                    "agent_ratio": str(cfg.agent_ratio),
                    "merchant_amount": str(merchant_amount),
                }

            settle_account = MerchantService().get_default_settlement_account(batch.merchant)
            to_account = info.get("to_account") or info.get("account_no") or ""
            if settle_account and not to_account:
                to_account = decrypt_field(settle_account.account_number) or ""
            if not to_account:
                to_account = "MERCHANT"
            from_account = info.get("from_account") or info.get("nostro_account") or "NOSTRO"
            currency = batch.currency or info.get("currency") or "CNY"
            bank_code = info.get("bank_code") or ""
            try:
                from apps.routing.services import RoutingService
                channel = RoutingService.route_select(float(merchant_amount), currency, "CN")
                if channel:
                    bank_code = channel.bank_code
                    info["routed_bank_code"] = bank_code
                from apps.routing.models import RoutingLog
                RoutingLog.objects.create(
                    order_no=batch.batch_no,
                    channel=channel,
                    amount=merchant_amount,
                    currency=currency,
                    result=RoutingLog.Result.SUCCESS if channel else RoutingLog.Result.FAILED,
                    request_data={"batch_no": batch.batch_no, "bank_code": bank_code},
                )
            except Exception:
                pass

            info["to_account"] = to_account
            info["currency"] = currency
            batch.settlement_account_info = info
            batch.save(update_fields=["settlement_account_info"])

            gateway = BankGatewayRouter.get_gateway(bank_code)
            logger.info(
                "settle.distribute batch=%s net=%s payout=%s bank=%s",
                batch.batch_no, batch.settle_net_amount, merchant_amount, bank_code,
            )
            result = gateway.transfer(
                from_account=from_account,
                to_account=to_account,
                amount=merchant_amount,
                currency=currency,
                transfer_no=batch.batch_no,
                remark=f"settlement {batch.batch_no}",
            )
            if not result.get("success"):
                raise Exception(result.get("message", "transfer failed"))

            bank_txn_id = result.get("bank_txn_id") or result.get("txn_id") or ""
            self._finalize_success(
                batch,
                merchant_amount=merchant_amount,
                currency=currency,
                bank_code=bank_code,
                bank_txn_id=bank_txn_id,
                from_account=from_account,
                to_account=to_account,
            )
        except Exception as e:
            batch.status = SettlementBatch.SettleStatus.FAILED
            batch.fail_reason = str(e)[:256]
            batch.save(update_fields=["status", "fail_reason"])
            logger.exception("settle.distribute failed batch=%s", batch.batch_no)

        return batch

    @transaction.atomic
    def _finalize_success(
        self, batch, *, merchant_amount, currency, bank_code, bank_txn_id, from_account, to_account
    ):
        now = timezone.now()
        batch.status = SettlementBatch.SettleStatus.SETTLED
        batch.settled_at = now
        batch.bank_txn_id = bank_txn_id or ""
        batch.save(update_fields=["status", "settled_at", "bank_txn_id"])

        order_ids = list(batch.details.values_list("payment_order_id", flat=True))
        PaymentOrder.objects.filter(pk__in=order_ids).update(
            status=PaymentOrder.OrderStatus.SETTLED,
            settled_at=now,
            completed_at=now,
        )

        MoneyMovementService().record(
            movement_type=MoneyMovement.MovementType.SETTLEMENT_PAYOUT,
            amount=merchant_amount,
            currency=currency,
            source_type="SETTLEMENT_BATCH",
            source_id=str(batch.id),
            status=MoneyMovement.MovementStatus.SUCCESS,
            evidence_level=(
                MoneyMovement.EvidenceLevel.BANK_CONFIRMED
                if bank_txn_id else MoneyMovement.EvidenceLevel.SYSTEM_CONFIRMED
            ),
            occurred_at=now,
            from_party_type="PLATFORM",
            from_account=from_account,
            to_party_type="MERCHANT",
            to_party_id=str(batch.merchant_id),
            to_account=to_account,
            bank_code=bank_code,
            bank_txn_id=bank_txn_id,
            settlement_batch=batch,
            remark=f"清算出款 {batch.batch_no}",
        )

        for detail in batch.details.select_related("payment_order"):
            order = detail.payment_order
            try:
                self._debit_merchant_va(order, batch)
            except Exception:
                logger.exception("VA debit skipped for order %s batch %s", order.order_no, batch.batch_no)

    def _debit_merchant_va(self, order: PaymentOrder, batch: SettlementBatch):
        self.account_service.debit_va_for_order_outflow(
            order,
            remark=f"清算出款 {batch.batch_no}",
        )
