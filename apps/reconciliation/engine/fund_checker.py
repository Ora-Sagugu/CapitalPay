"""对账引擎 — 资金核对。"""
from decimal import Decimal
from django.db.models import Sum
from apps.account.models import NostroAccount
from apps.payment.models import PaymentOrder, RefundOrder
from apps.settlement.models import SettlementBatch
from ..models import NostroBalanceCheck


class FundChecker:
    """资金核对引擎。

    核对逻辑:
        平台账面余额 = 期初余额 + 本期收款 - 本期退款 - 本期结算付出 + 调拨入 - 调拨出
        差额 = 银行对账单余额 - 平台账面余额
    """

    def check_nostro_balance(self, nostro_account: NostroAccount, bank_statement_balance: Decimal) -> NostroBalanceCheck:
        """核对单个 nostro 账户余额。

        Args:
            nostro_account: Nostro 账户
            bank_statement_balance: 银行对账单显示的余额

        Returns:
            NostroBalanceCheck 记录
        """
        from django.utils import timezone
        today = timezone.now().date()

        # 平台账面余额
        platform_balance = nostro_account.balance

        # 差额
        difference = bank_statement_balance - platform_balance

        check = NostroBalanceCheck.objects.create(
            check_date=today,
            nostro_account=nostro_account,
            platform_balance=platform_balance,
            bank_statement_balance=bank_statement_balance,
            difference=difference,
            is_balanced=(difference == 0),
            remark="" if difference == 0 else f"差额 {difference}，需进一步核查",
        )

        # 更新 nostro 账户对账信息
        nostro_account.last_reconciled_balance = bank_statement_balance
        nostro_account.last_reconciled_at = timezone.now()
        nostro_account.save(update_fields=["last_reconciled_balance", "last_reconciled_at"])

        return check

    def calculate_expected_balance(
        self,
        account: NostroAccount,
        start_date,
        end_date,
    ) -> Decimal:
        """计算指定期间的预期账面余额变动。

        Returns:
            {"collections": Decimal, "refunds": Decimal, "settlements": Decimal, "net": Decimal}
        """
        # 本期收款
        collections = PaymentOrder.objects.filter(
            pay_received_at__date__gte=start_date,
            pay_received_at__date__lte=end_date,
            status__in=[
                PaymentOrder.OrderStatus.PAY_RECEIVED,
                PaymentOrder.OrderStatus.PENDING_SETTLE,
                PaymentOrder.OrderStatus.SETTLED,
            ],
            bank_code=account.bank_code,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        # 本期退款
        refunds = RefundOrder.objects.filter(
            refunded_at__date__gte=start_date,
            refunded_at__date__lte=end_date,
            status=RefundOrder.RefundStatus.SUCCESS,
            payment_order__bank_code=account.bank_code,
        ).aggregate(total=Sum("refund_amount"))["total"] or Decimal("0")

        # 本期结算付出
        settlements = SettlementBatch.objects.filter(
            settled_at__date__gte=start_date,
            settled_at__date__lte=end_date,
            status="SETTLED",
        ).aggregate(total=Sum("settle_net_amount"))["total"] or Decimal("0")

        net_change = collections - refunds - settlements

        return {
            "collections": collections,
            "refunds": refunds,
            "settlements": settlements,
            "net": net_change,
        }
