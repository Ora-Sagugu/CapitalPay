"""清算引擎 — 资金划拨。

功能清单对应:
    - nostro账户资金调拨
    - 商户分账结算（资金划拨到商户结算账户）
"""
import logging

from django.conf import settings
from django.utils import timezone

from ..models import SettlementBatch
from apps.account.services import AccountService
from apps.payment.gateway import BankGatewayRouter

logger = logging.getLogger(__name__)


class FundsDistributor:
    """资金划拨器 — 将净结算金额打款到商户结算账户。"""

    def __init__(self):
        self.account_service = AccountService()

    def distribute(self, batch: SettlementBatch) -> SettlementBatch:
        """执行资金划拨。"""
        if batch.status != SettlementBatch.SettleStatus.PENDING:
            from apps.core.exceptions import BusinessException
            raise BusinessException("SETTLE_STATUS_INVALID", "清算批次状态不可划拨")

        batch.status = SettlementBatch.SettleStatus.PROCESSING
        batch.save(update_fields=["status"])

        try:
            info = batch.settlement_account_info or {}
            bank_code = info.get("bank_code") or settings.BANK_CODES[0]
            gateway = BankGatewayRouter.get_gateway(bank_code)
            from_account = info.get("from_account") or info.get("nostro_account") or "NOSTRO"
            to_account = info.get("to_account") or info.get("account_no") or "MERCHANT"
            currency = info.get("currency") or "CNY"
            logger.info(
                "settle.distribute batch=%s net=%s bank=%s",
                batch.batch_no, batch.settle_net_amount, bank_code,
            )
            result = gateway.transfer(
                from_account=from_account,
                to_account=to_account,
                amount=batch.settle_net_amount,
                currency=currency,
                transfer_no=batch.batch_no,
                remark=f"settlement {batch.batch_no}",
            )
            if not result.get("success"):
                raise Exception(result.get("message", "transfer failed"))

            batch.status = SettlementBatch.SettleStatus.SETTLED
            batch.settled_at = timezone.now()
            batch.save(update_fields=["status", "settled_at"])

        except Exception as e:
            batch.status = SettlementBatch.SettleStatus.FAILED
            batch.fail_reason = str(e)[:256]
            batch.save(update_fields=["status", "fail_reason"])

        return batch
