"""模拟银行网关 — 开发 / 测试默认实现。"""
import logging
from decimal import Decimal

from .base import BaseBankGateway

logger = logging.getLogger(__name__)


class MockBankGateway(BaseBankGateway):
    """模拟银行网关 — 所有操作直接成功。"""

    bank_code = "MOCK"
    bank_name = "模拟银行"

    def pay(self, order) -> dict:
        logger.info("bank.MOCK.pay order=%s", getattr(order, "order_no", order))
        return {
            "success": True,
            "pay_url": f"https://mock-bank.example.com/pay?order={order.order_no}",
            "message": "ok",
        }

    def query(self, order_or_txn_id) -> dict:
        order_no = order_or_txn_id if isinstance(order_or_txn_id, str) else order_or_txn_id.order_no
        amount = getattr(order_or_txn_id, "amount", None)
        logger.info("bank.MOCK.query order=%s", order_no)
        return {
            "success": True,
            "status": "SUCCESS",
            "txn_id": f"MOCK_TXN_{order_no}",
            "amount": Decimal(str(amount)) if amount is not None else Decimal("0"),
        }

    def refund(self, *, origin_txn_id: str, refund_amount: Decimal, refund_no: str) -> dict:
        logger.info("bank.MOCK.refund refund_no=%s amount=%s", refund_no, refund_amount)
        return {
            "success": True,
            "bank_refund_id": f"MOCK_REFUND_{refund_no}",
            "message": "ok",
        }

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
        logger.info(
            "bank.MOCK.transfer no=%s amount=%s %s -> %s",
            transfer_no, amount, from_account, to_account,
        )
        return {
            "success": True,
            "bank_txn_id": f"MOCK_TRF_{transfer_no}",
            "message": "ok",
        }

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
        logger.info(
            "bank.MOCK.disburse no=%s amount=%s payee=%s",
            disbursement_no, amount, payee_account_no,
        )
        return {
            "success": True,
            "bank_txn_id": f"MOCK_DISB_{disbursement_no}",
            "message": "ok",
        }

    def request_adjustment(
        self,
        *,
        bank_txn_id: str,
        amount: Decimal,
        reason: str,
        diff_id: str,
    ) -> dict:
        logger.info("bank.MOCK.adjust diff=%s txn=%s amount=%s", diff_id, bank_txn_id, amount)
        return {
            "success": True,
            "bank_txn_id": f"MOCK_ADJ_{diff_id}",
            "message": "ok",
        }
