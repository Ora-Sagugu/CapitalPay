"""真实银行网关壳 — 凭证未配置前显式 NotImplementedError。"""
import logging
from decimal import Decimal

from django.conf import settings

from .base import BaseBankGateway

logger = logging.getLogger(__name__)


class RealBankGateway(BaseBankGateway):
    """生产银行适配器占位。

    在 BANK_GATEWAY_MODE=REAL 且未配置对应凭证时，所有调用失败并记录日志，
    禁止静默伪造成功。
    """

    def __init__(self, bank_code: str, bank_name: str = ""):
        self.bank_code = bank_code
        self.bank_name = bank_name or f"{bank_code}银行"

    def _ensure_configured(self, op: str):
        # 预留：按 bank_code 检查 API Key / 证书等
        configured = bool(getattr(settings, "BANK_API_KEYS", {}).get(self.bank_code))
        if not configured:
            logger.warning("bank.%s.%s blocked: credentials missing", self.bank_code, op)
            raise NotImplementedError(f"{self.bank_code}.{op} not configured")

    def pay(self, order) -> dict:
        self._ensure_configured("pay")
        raise NotImplementedError(f"{self.bank_code}.pay not implemented")

    def query(self, order_or_txn_id) -> dict:
        self._ensure_configured("query")
        raise NotImplementedError(f"{self.bank_code}.query not implemented")

    def refund(self, *, origin_txn_id: str, refund_amount: Decimal, refund_no: str) -> dict:
        self._ensure_configured("refund")
        raise NotImplementedError(f"{self.bank_code}.refund not implemented")

    def transfer(
        self,
        *,
        from_account: str,
        to_account: str,
        amount: Decimal,
        currency: str,
        transfer_no: str,
        remark: str = "",
    ) -> dict:
        self._ensure_configured("transfer")
        raise NotImplementedError(f"{self.bank_code}.transfer not implemented")

    def disburse(
        self,
        *,
        payee_bank_name: str,
        payee_account_no: str,
        payee_account_holder: str,
        amount: Decimal,
        currency: str,
        disbursement_no: str,
        swift_code: str = "",
        remark: str = "",
    ) -> dict:
        self._ensure_configured("disburse")
        raise NotImplementedError(f"{self.bank_code}.disburse not implemented")

    def request_adjustment(
        self,
        *,
        bank_txn_id: str,
        amount: Decimal,
        reason: str,
        diff_id: str,
    ) -> dict:
        self._ensure_configured("request_adjustment")
        raise NotImplementedError(f"{self.bank_code}.request_adjustment not implemented")
