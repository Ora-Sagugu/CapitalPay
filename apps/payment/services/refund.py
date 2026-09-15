"""支付交易 — 退款服务。"""
from decimal import Decimal
from django.db import models as dm
from django.db import transaction
from django.utils import timezone
from apps.core.exceptions import BusinessException, ErrorCode
from apps.core.utils import generate_order_no
from ..models import PaymentOrder, RefundOrder, RefundFeeConfig
from ..gateway import BankGatewayRouter


class RefundService:
    """退款服务。

    功能清单对应:
        - 退款申请 / 退款查询 (商户服务)
        - 退款审核 / 退款查询 (运营管理)
    """

    @transaction.atomic
    def request_refund(
        self,
        *,
        payment_order: PaymentOrder,
        refund_amount: Decimal,
        reason: str,
        idempotency_key: str = None,
    ) -> RefundOrder:
        """发起退款申请 → 进入待审核。

        Args:
            payment_order: 原支付订单
            refund_amount: 退款金额
            reason: 退款原因
            idempotency_key: 幂等键
        """
        # ── 校验订单状态 ──
        valid_statuses = [
            PaymentOrder.OrderStatus.PENDING_PAY,
            PaymentOrder.OrderStatus.PAY_RECEIVED,
            PaymentOrder.OrderStatus.PENDING_SETTLE,
            PaymentOrder.OrderStatus.SETTLED,
            PaymentOrder.OrderStatus.COMPLETED,
            PaymentOrder.OrderStatus.REFUNDING,
        ]
        if payment_order.status not in valid_statuses:
            raise BusinessException(ErrorCode.ORDER_STATUS_INVALID, "The current instruction status does not permit a refund")

        # ── 校验退款金额 ──
        refunded_total = RefundOrder.objects.filter(
            payment_order=payment_order,
            status__in=[
                RefundOrder.RefundStatus.PENDING_REVIEW,
                RefundOrder.RefundStatus.APPROVED,
                RefundOrder.RefundStatus.PROCESSING,
                RefundOrder.RefundStatus.SUCCESS,
            ],
            is_deleted=False,
        ).aggregate(total=dm.Sum("refund_amount"))["total"] or Decimal("0")

        if refunded_total + refund_amount > payment_order.amount:
            raise BusinessException(ErrorCode.REFUND_EXCEED_AMOUNT)

        if refund_amount <= 0:
            raise BusinessException("REFUND_AMOUNT_INVALID", "The refund amount must be greater than zero")

        # ── 创建退款单 ──
        fee_rate = Decimal(str(RefundFeeConfig.get_fee_rate() or 0))
        refund_amount = Decimal(str(refund_amount))
        fee_amount = (refund_amount * fee_rate / Decimal("100")).quantize(Decimal("0.01"))

        refund = RefundOrder(
            refund_no=generate_order_no("R"),
            payment_order=payment_order,
            refund_amount=refund_amount,
            refund_fee_rate=fee_rate,
            refund_fee_amount=fee_amount,
            refund_reason=reason,
            status=RefundOrder.RefundStatus.PENDING_REVIEW,
        )
        refund.save()

        # 更新原订单状态
        payment_order.status = PaymentOrder.OrderStatus.REFUNDING
        payment_order.add_status_history(PaymentOrder.OrderStatus.REFUNDING, {
            "refund_no": refund.refund_no,
            "refund_amount": str(refund_amount),
        })
        payment_order.save(update_fields=["status", "status_history"])

        return refund

    def approve_refund(self, refund: RefundOrder, reviewer: str) -> RefundOrder:
        """审核通过。"""
        if refund.status != RefundOrder.RefundStatus.PENDING_REVIEW:
            raise BusinessException(ErrorCode.ORDER_STATUS_INVALID, "The refund instruction is not in a reviewable status")

        refund.status = RefundOrder.RefundStatus.APPROVED
        refund.reviewed_by = reviewer
        refund.reviewed_at = timezone.now()
        refund.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        # 同步执行退款
        from ..tasks import execute_refund_task
        execute_refund_task(str(refund.id))
        return refund

    def reject_refund(self, refund: RefundOrder, reviewer: str, reason: str = "") -> RefundOrder:
        """审核驳回。"""
        if refund.status != RefundOrder.RefundStatus.PENDING_REVIEW:
            raise BusinessException(ErrorCode.ORDER_STATUS_INVALID)

        refund.status = RefundOrder.RefundStatus.REJECTED
        refund.reviewed_by = reviewer
        refund.reviewed_at = timezone.now()
        refund.fail_reason = reason
        refund.save(update_fields=["status", "reviewed_by", "reviewed_at", "fail_reason"])

        # 恢复原订单状态（从 status_history 中找到 REFUNDING 之前的状态）
        payment_order = refund.payment_order
        if payment_order.status == PaymentOrder.OrderStatus.REFUNDING:
            successful_refunds = payment_order.refunds.filter(
                status=RefundOrder.RefundStatus.SUCCESS, is_deleted=False
            ).exists()
            if not successful_refunds:
                # 尝试从状态历史中恢复原始状态
                prev_status = self._get_previous_status(payment_order)
                payment_order.status = prev_status
                payment_order.save(update_fields=["status"])

        return refund

    @staticmethod
    def _get_previous_status(order: PaymentOrder) -> str:
        """从 status_history 中找到 REFUNDING 之前的最后一个状态。"""
        history = order.status_history or []
        for entry in reversed(history):
            if isinstance(entry, dict):
                s = entry.get("status", "")
                if s and s != PaymentOrder.OrderStatus.REFUNDING and s in PaymentOrder.OrderStatus.values:
                    return s
        # 无法确定原始状态时，回退到安全的默认值
        return PaymentOrder.OrderStatus.PAY_RECEIVED

    @transaction.atomic
    def execute_refund(self, refund: RefundOrder) -> RefundOrder:
        """执行退款 — 调用银行网关。

        由 Celery 异步任务调用。
        """
        refund.status = RefundOrder.RefundStatus.PROCESSING
        refund.save(update_fields=["status"])

        order = refund.payment_order
        try:
            gateway = BankGatewayRouter.get_gateway(order.bank_code)
            result = gateway.refund(
                origin_txn_id=order.bank_txn_id,
                refund_amount=refund.refund_amount,
                refund_no=refund.refund_no,
            )

            if result.get("success"):
                refund.status = RefundOrder.RefundStatus.SUCCESS
                refund.bank_refund_id = result.get("bank_refund_id", "")
                refund.refunded_at = timezone.now()
                refund.save(update_fields=["status", "bank_refund_id", "refunded_at"])
                self._record_refund_movement(refund, order)
                self._reverse_collection_ledger(refund, order)

                # 检查是否全额退款完成
                if self._is_fully_refunded(order):
                    order.status = PaymentOrder.OrderStatus.REFUNDED
                    order.save(update_fields=["status"])
            else:
                refund.status = RefundOrder.RefundStatus.FAILED
                refund.fail_reason = result.get("message", "The bank refund was unsuccessful")
                refund.save(update_fields=["status", "fail_reason"])

        except Exception as e:
            refund.status = RefundOrder.RefundStatus.FAILED
            refund.fail_reason = str(e)
            refund.save(update_fields=["status", "fail_reason"])

        return refund

    def _record_refund_movement(self, refund: RefundOrder, order: PaymentOrder):
        from apps.account.models import MoneyMovement
        from apps.account.money_movements import MoneyMovementService

        MoneyMovementService().record(
            movement_type=MoneyMovement.MovementType.REFUND,
            amount=refund.refund_amount,
            currency=order.from_currency or order.currency or "",
            source_type="REFUND",
            source_id=str(refund.id),
            status=MoneyMovement.MovementStatus.SUCCESS,
            evidence_level=(
                MoneyMovement.EvidenceLevel.BANK_CONFIRMED
                if refund.bank_refund_id
                else MoneyMovement.EvidenceLevel.SYSTEM_CONFIRMED
            ),
            occurred_at=refund.refunded_at,
            from_party_type="PLATFORM",
            to_party_type="PAYER",
            to_party_id=order.user_id or "",
            bank_code=order.bank_code or "",
            bank_txn_id=refund.bank_refund_id or "",
            payment_order=order,
            refund_order=refund,
            remark=f"Refund {refund.refund_no}",
        )

    def _reverse_collection_ledger(self, refund: RefundOrder, order: PaymentOrder):
        from apps.account.models import VaLedgerEntry
        from apps.account.services import AccountService

        credit = (
            VaLedgerEntry.objects.filter(
                order=order,
                entry_type=VaLedgerEntry.EntryType.CREDIT,
                source_type="PAYMENT",
                is_deleted=False,
            )
            .select_related("virtual_account")
            .first()
        )
        if not credit:
            return
        try:
            AccountService().post_va_entry(
                virtual_account=credit.virtual_account,
                amount=refund.refund_amount,
                entry_type=VaLedgerEntry.EntryType.DEBIT,
                order=order,
                remark=f"Refund reversal {refund.refund_no}",
                source_type="REFUND",
                source_id=str(refund.id),
            )
            AccountService().debit_agent_pool_for_outflow(
                merchant=order.merchant,
                amount=refund.refund_amount,
                currency=credit.virtual_account.currency or order.currency or "CNY",
                origin_source="REFUND",
                origin_id=str(refund.id),
                remark=f"Refund {refund.refund_no}",
            )
        except Exception:
            pass

    def _is_fully_refunded(self, order: PaymentOrder) -> bool:
        """检查订单是否已全额退款。"""
        refunded = RefundOrder.objects.filter(
            payment_order=order,
            status=RefundOrder.RefundStatus.SUCCESS,
            is_deleted=False,
        ).aggregate(total=dm.Sum("refund_amount"))["total"] or Decimal("0")
        return refunded == order.amount

    def get_refund_by_no(self, refund_no: str) -> RefundOrder:
        """按退款单号查询。"""
        try:
            return RefundOrder.objects.get(refund_no=refund_no, is_deleted=False)
        except RefundOrder.DoesNotExist:
            raise BusinessException("REFUND_NOT_FOUND", "The refund instruction does not exist")
