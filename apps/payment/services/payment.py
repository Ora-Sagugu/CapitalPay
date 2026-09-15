"""支付交易 — 支付确认服务。"""
from __future__ import annotations
import re
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.core.exceptions import BusinessException, ErrorCode
from ..models import PaymentOrder
from ..gateway import BankGatewayRouter
from .prn_service import extract_prn_from_remark


class PaymentConfirmService:
    """收款确认服务。

    匹配规则（优先级从高到低）:
    1. PRN 码精确匹配 — 附言中 PRN 与订单 prn_code 一致
    2. UIN 精确匹配 — 附言中 UIN 与订单唯一识别号一致
    3. 金额 + 时间窗口模糊匹配
    """

    UIN_PATTERN = re.compile(r"UIN\d{17}")
    PRN_PATTERN = re.compile(r"(?:PRN|prn)[:：\s]*([A-Za-z0-9]\d{5})|(?:^|\s)([A-Za-z0-9]\d{5})(?:\s|$)")

    def auto_match_wire_transfer(self, bank_statement_line: dict) -> PaymentOrder | None:
        """银行流水到达 → 自动匹配订单。

        Args:
            bank_statement_line: {
                "txn_id": str,       # 银行交易流水号
                "amount": Decimal,   # 金额
                "remark": str,       # 附言
                "txn_time": datetime,# 交易时间
                "bank_code": str,    # 银行编码
            }

        Returns:
            匹配到的 PaymentOrder，或 None
        """
        remark = bank_statement_line.get("remark", "")
        bank_amount = Decimal(str(bank_statement_line["amount"]))

        # ── 规则 1: PRN 精确匹配 ──
        prn_code = self._extract_prn(remark)
        if prn_code:
            order = PaymentOrder.objects.filter(
                prn_code__iexact=prn_code,
                status__in=[
                    PaymentOrder.OrderStatus.PENDING_PAY,
                ],
            ).first()
            if order:
                return self._confirm_payment(order, bank_statement_line, prn_code)

        # ── 规则 2: UIN 精确匹配 ──
        uin_match = self.UIN_PATTERN.search(remark)
        if uin_match:
            uin = uin_match.group()
            order = PaymentOrder.objects.filter(
                unique_identification_no=uin,
                status__in=[
                    PaymentOrder.OrderStatus.PRE_CREATE,
                    PaymentOrder.OrderStatus.PENDING_PAY,
                ],
            ).first()
            if order:
                return self._confirm_payment(order, bank_statement_line)

        # ── 规则 3: 金额 + 时间窗口模糊匹配 ──
        bank_time = bank_statement_line["txn_time"]
        candidates = PaymentOrder.objects.filter(
            amount=bank_amount,
            status__in=[
                PaymentOrder.OrderStatus.PRE_CREATE,
                PaymentOrder.OrderStatus.PENDING_PAY,
            ],
            pay_method=PaymentOrder.PayMethod.WIRE_TRANSFER,
            created_at__gte=bank_time - timezone.timedelta(hours=24),
            created_at__lte=bank_time + timezone.timedelta(hours=1),
        ).order_by("created_at")

        if candidates.exists():
            return self._confirm_payment(candidates.first(), bank_statement_line)

        return None

    def manual_confirm(self, order_id: str, user_id: str = None, bank_txn_id: str = None) -> PaymentOrder:
        """用户或运营手动关联汇款 → 确认收款。

        功能清单对应: 用户汇款确认
        """
        qs = PaymentOrder.objects.filter(id=order_id)
        if user_id:
            qs = qs.filter(user_id=user_id)
        order = qs.first()
        if not order:
            raise BusinessException(ErrorCode.ORDER_NOT_FOUND)

        if order.status not in {
            PaymentOrder.OrderStatus.PRE_CREATE,
            PaymentOrder.OrderStatus.PENDING_PAY,
        }:
            raise BusinessException(ErrorCode.ORDER_STATUS_INVALID)

        return self._confirm_payment(order, {"txn_id": bank_txn_id or "", "amount": order.amount})

    def manual_confirm_by_order_no(self, order_no: str, bank_txn_id: str = None, user_id: str = None) -> PaymentOrder:
        order = PaymentOrder.objects.filter(order_no=order_no, is_deleted=False).first()
        if not order:
            raise BusinessException(ErrorCode.ORDER_NOT_FOUND)
        if user_id and str(order.user_id or "") != str(user_id):
            raise BusinessException("PERMISSION_DENIED", "The authenticated principal is not authorised to confirm this instruction", 403)
        return self.manual_confirm(str(order.id), user_id=user_id, bank_txn_id=bank_txn_id)

    @staticmethod
    def _extract_prn(remark: str) -> str | None:
        """从附言中提取 6 位 PRN 码。"""
        return extract_prn_from_remark(remark)

    @transaction.atomic
    def _confirm_payment(
        self, order: PaymentOrder, bank_info: dict, prn_code: str | None = None
    ) -> PaymentOrder:
        """执行收款确认 — 加行锁防止并发。

        Phase 5: Payment Confirmation & Reconciliation
        - 银行流水到达 → PRN 匹配 → 确认收款
        - 金额一致 → PAY_RECEIVED，创建交易记录
        - 通知 Payment Received (Status: CONFIRMED)
        """
        order = PaymentOrder.objects.select_for_update().select_related("merchant").get(pk=order.pk)

        # 待审核订单绝不能通过银行匹配绕过运营审核。
        confirmable = {
            PaymentOrder.OrderStatus.PRE_CREATE,
            PaymentOrder.OrderStatus.PENDING_PAY,
        }
        if order.status not in confirmable:
            raise BusinessException(ErrorCode.ORDER_STATUS_INVALID)

        from .remittance_policy import RemittanceEligibilityPolicy
        RemittanceEligibilityPolicy.assert_can_continue_existing(order.merchant)

        bank_txn_id = bank_info.get("txn_id", "")
        bank_amount = bank_info.get("amount", order.amount)

        # 金额校验
        if Decimal(str(bank_amount)) != order.amount:
            raise BusinessException(
                ErrorCode.ORDER_AMOUNT_MISMATCH,
                f"The bank amount {bank_amount} does not match the instruction amount {order.amount}",
            )

        now = timezone.now()
        order.status = PaymentOrder.OrderStatus.PAY_RECEIVED
        order.pay_received_at = now
        order.bank_txn_id = bank_txn_id
        extra = {"bank_txn_id": bank_txn_id}
        if prn_code:
            extra["prn_matched"] = True
            extra["prn_code"] = prn_code
        from .remittance_application import arm_agent_payout_request
        arm_agent_payout_request(order)
        if order.agent_payout_request_status == PaymentOrder.AgentPayoutRequestStatus.PENDING:
            extra["agent_payout_request"] = "pending"
        order.add_status_history(PaymentOrder.OrderStatus.PAY_RECEIVED, extra)
        order.save(update_fields=[
            "status", "pay_received_at", "bank_txn_id", "status_history",
            "agent_payout_request_status",
        ])

        self._credit_virtual_account(order)
        # ── 费用分账：手续费记入机构账户 ──
        self._credit_fees_to_agency(order)
        self._record_collection_movement(order, bank_txn_id)
        self._record_user_payment_detail(order)
        from .prn_service import mark_prn_matched
        mark_prn_matched(order.prn_code or prn_code, order)
        from .notify import trigger_order_notify
        trigger_order_notify(order)

        return order

    @staticmethod
    def _collection_currency(order: PaymentOrder) -> str:
        """Remittance principal is in from_currency; pre-orders keep amount in order.currency.

        PaymentOrder.from_currency defaults to USD even when unused, so only trust it on
        remittance snapshots (quote or beneficiary details).
        """
        is_remittance = bool(
            getattr(order, "quote_id", None) or (order.beneficiary_name or "").strip()
        )
        if is_remittance and order.from_currency:
            return order.from_currency.strip().upper()
        return (order.currency or order.from_currency or order.to_currency or "CNY").strip().upper() or "CNY"

    def _credit_virtual_account(self, order: PaymentOrder):
        """收款确认后贷记商户 VA 分类账（汇出币种本金）。"""
        from apps.account.services import AccountService

        svc = AccountService()
        va = svc.merchant_va_for_currency(order.merchant, self._collection_currency(order))
        if not va:
            return
        svc.post_va_entry(
            virtual_account=va,
            amount=order.amount,
            entry_type="CREDIT",
            order=order,
            remark=f"Collection confirmed {order.order_no}",
            source_type="PAYMENT",
            source_id=str(order.id),
        )

    def _credit_fees_to_agency(self, order: PaymentOrder):
        """费用分账 — 将手续费记入代理手续费账户。"""
        from django.conf import settings
        if not getattr(settings, "ENABLE_AGENTS", True):
            return
        fee = order.fee_amount
        if not fee or fee <= 0:
            return
        agent = getattr(order.merchant, "agent", None)
        if agent:
            from apps.account.models import NostroAccount, VaLedgerEntry
            from apps.account.services import AccountService
            from apps.agent.services import ensure_agent_accounts, get_agent_ledger_va

            currency = self._collection_currency(order)
            ensure_agent_accounts(agent, currency)
            va = get_agent_ledger_va(agent, NostroAccount.AccountType.FEE, currency)
            if va:
                AccountService().post_va_entry(
                    virtual_account=va,
                    amount=fee,
                    entry_type=VaLedgerEntry.EntryType.CREDIT,
                    order=order,
                    remark=f"Charges {order.order_no}",
                    source_type="FEE",
                    source_id=str(order.id),
                )
        order.add_status_history("FEES_CREDITED", {
            "fee_amount": str(fee),
            "merchant": order.merchant.merchant_no,
            "note": "Charges have been posted to the institution account",
        })
        order.save(update_fields=["status_history", "updated_at"])

    def _record_collection_movement(self, order: PaymentOrder, bank_txn_id: str):
        """写入不可变收款流水。"""
        from apps.account.models import MoneyMovement
        from apps.account.money_movements import MoneyMovementService

        currency = order.from_currency or order.currency or ""
        evidence = (
            MoneyMovement.EvidenceLevel.BANK_CONFIRMED
            if bank_txn_id
            else MoneyMovement.EvidenceLevel.SYSTEM_CONFIRMED
        )
        MoneyMovementService().record(
            movement_type=MoneyMovement.MovementType.COLLECTION,
            amount=order.amount,
            currency=currency,
            source_type="PAYMENT",
            source_id=str(order.id),
            status=MoneyMovement.MovementStatus.SUCCESS,
            evidence_level=evidence,
            occurred_at=order.pay_received_at,
            from_party_type="PAYER",
            from_party_id=order.user_id or "",
            to_party_type="MERCHANT",
            to_party_id=str(order.merchant_id or ""),
            bank_code=order.bank_code or "",
            bank_txn_id=bank_txn_id or "",
            payment_order=order,
            remark=f"System-confirmed collection {order.order_no}",
        )

    def _record_user_payment_detail(self, order: PaymentOrder):
        if not order.user_id:
            return
        try:
            from apps.account.services import AccountService
            AccountService().record_payment_detail(order, order.user_id)
        except Exception:
            pass
