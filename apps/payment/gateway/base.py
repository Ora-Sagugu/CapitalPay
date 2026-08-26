"""银行网关 — 抽象基类。

所有银行适配器必须实现此接口。返回约定:
    {"success": bool, "message": str, ...业务字段}
"""
from abc import ABC, abstractmethod
from decimal import Decimal


class BaseBankGateway(ABC):
    """银行网关抽象基类。"""

    bank_code: str
    bank_name: str

    @abstractmethod
    def pay(self, order) -> dict:
        """发起支付 — 返回支付页面 URL 或表单。"""
        ...

    @abstractmethod
    def query(self, order_or_txn_id) -> dict:
        """查询支付结果。"""
        ...

    @abstractmethod
    def refund(self, *, origin_txn_id: str, refund_amount: Decimal, refund_no: str) -> dict:
        """发起退款。"""
        ...

    @abstractmethod
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
        """账户间转账 / 清算出款。"""
        ...

    @abstractmethod
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
        """代付 / 代理商拨付。"""
        ...

    @abstractmethod
    def request_adjustment(
        self,
        *,
        bank_txn_id: str,
        amount: Decimal,
        reason: str,
        diff_id: str,
    ) -> dict:
        """向银行发起对账差错调账。"""
        ...

    def name(self) -> str:
        return self.bank_name
