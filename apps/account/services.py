"""账户体系 — 业务服务层。"""
from __future__ import annotations
import uuid
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.core.exceptions import BusinessException, ErrorCode
from apps.core.utils import generate_batch_no, encrypt_field, decrypt_field
from .models import (
    NostroAccount, UserAccount, FundTransfer, UserPaymentDetail, DepositRequest,
    AgentDisbursement, DisbursementApproval, VirtualAccount, VaLedgerEntry,
)


class AccountService:
    """账户管理服务。"""

    # ── Nostro 账户 ─────────────────────────────────────────

    def get_active_collection_accounts(self, bank_code: str = None) -> list[NostroAccount]:
        """获取启用的收款账户。"""
        qs = NostroAccount.objects.filter(
            is_active=True, is_deleted=False,
            account_type=NostroAccount.AccountType.COLLECTION,
        )
        if bank_code:
            qs = qs.filter(bank_code=bank_code)
        return list(qs)

    def get_settlement_account(self, bank_code: str) -> NostroAccount | None:
        """获取结算用 nostro 账户。"""
        return NostroAccount.objects.filter(
            bank_code=bank_code,
            account_type=NostroAccount.AccountType.SETTLEMENT,
            is_active=True, is_deleted=False,
        ).first()

    def update_balance(self, account: NostroAccount, amount: Decimal, is_credit: bool = True):
        """更新 nostro 账户余额（credit=True: 增加, False: 减少）。"""
        with transaction.atomic():
            account = NostroAccount.objects.select_for_update().get(pk=account.pk)
            if is_credit:
                account.balance += amount
            else:
                if account.balance < amount:
                    raise BusinessException(ErrorCode.INSUFFICIENT_BALANCE)
                account.balance -= amount
            account.save(update_fields=["balance"])

    # ── 用户账户 ────────────────────────────────────────────

    @transaction.atomic
    def bind_account(
        self,
        *,
        user_id: str,
        merchant_id,
        bank_code: str,
        bank_name: str,
        account_holder: str,
        account_number: str,
        bind_token: str,
    ) -> UserAccount:
        """绑定用户银行账户（授权支付）。"""
        user_account = UserAccount(
            user_id=user_id,
            merchant=merchant_id if hasattr(merchant_id, "id") else merchant_id,
            bank_code=bank_code,
            bank_name=bank_name,
            account_holder=account_holder,
            account_number=encrypt_field(account_number),
            bind_token=encrypt_field(bind_token or uuid.uuid4().hex),
            status=UserAccount.BindStatus.ACTIVE,
            bind_at=timezone.now(),
        )
        user_account.save()
        return user_account

    def get_user_accounts(self, user_id: str) -> list[UserAccount]:
        """获取用户已绑定的账户列表。"""
        return list(UserAccount.objects.filter(
            user_id=user_id, status=UserAccount.BindStatus.ACTIVE, is_deleted=False
        ))

    # ── 资金调拨 ────────────────────────────────────────────

    @transaction.atomic
    def create_transfer(
        self,
        *,
        from_account: NostroAccount,
        to_account: NostroAccount,
        amount: Decimal,
        remark: str = "",
    ) -> FundTransfer:
        """创建资金调拨记录。"""
        if from_account.id == to_account.id:
            raise BusinessException("TRANSFER_SAME_ACCOUNT", "A transfer cannot be effected between the same account")

        transfer = FundTransfer(
            transfer_no=generate_batch_no("T"),
            from_account=from_account,
            to_account=to_account,
            amount=amount,
            currency=from_account.currency or "CNY",
            remark=remark,
            status=FundTransfer.TransferStatus.PENDING,
        )
        transfer.save()
        return transfer

    @transaction.atomic
    def execute_transfer(self, transfer: FundTransfer) -> FundTransfer:
        """执行资金调拨。"""
        if transfer.status != FundTransfer.TransferStatus.PENDING:
            raise BusinessException("TRANSFER_STATUS_INVALID")

        transfer = FundTransfer.objects.select_for_update().get(pk=transfer.pk)

        from apps.payment.gateway import BankGatewayRouter
        gateway = BankGatewayRouter.get_gateway(transfer.from_account.bank_code)
        result = gateway.transfer(
            from_account=transfer.from_account.account_no,
            to_account=transfer.to_account.account_no,
            amount=transfer.amount,
            currency=transfer.from_account.currency or "CNY",
            transfer_no=transfer.transfer_no,
            remark=transfer.remark or "",
        )
        if not result.get("success"):
            transfer.status = FundTransfer.TransferStatus.FAILED
            transfer.save(update_fields=["status"])
            raise BusinessException("TRANSFER_FAILED", result.get("message", "The transfer could not be completed"))

        # 调出账户扣减
        self.update_balance(transfer.from_account, transfer.amount, is_credit=False)
        # 调入账户增加
        self.update_balance(transfer.to_account, transfer.amount, is_credit=True)

        transfer.status = FundTransfer.TransferStatus.SUCCESS
        transfer.executed_at = timezone.now()
        transfer.save(update_fields=["status", "executed_at"])

        return transfer

    # ── 支付明细 ────────────────────────────────────────────

    def record_payment_detail(self, order, user_id: str, account: UserAccount = None) -> UserPaymentDetail:
        """记录用户支付明细。"""
        detail = UserPaymentDetail.objects.create(
            user_id=user_id,
            order=order,
            account=account,
            pay_method=order.pay_method,
            amount=order.amount,
            pay_time=order.pay_received_at or timezone.now(),
        )
        return detail

    def get_user_payment_history(self, user_id: str) -> list[UserPaymentDetail]:
        """获取用户支付历史。"""
        return list(UserPaymentDetail.objects.filter(
            user_id=user_id, is_deleted=False
        ).select_related("order").order_by("-pay_time"))

    @transaction.atomic
    def post_va_entry(
        self,
        *,
        virtual_account: VirtualAccount,
        amount: Decimal,
        entry_type: str,
        order=None,
        remark: str = "",
        source_type: str = "PAYMENT",
        source_id: str = "",
        update_master: bool = True,
    ) -> VaLedgerEntry:
        """写入 VA 分类账并更新余额；同一 source 幂等。"""
        amount = Decimal(str(amount))
        if amount <= 0:
            raise BusinessException("LEDGER_AMOUNT_INVALID", "The ledger entry amount must be a positive figure")

        src_id = source_id or (str(order.id) if order else "")
        if src_id:
            existing = VaLedgerEntry.objects.filter(
                source_type=source_type,
                source_id=src_id,
                entry_type=entry_type,
                is_deleted=False,
            ).first()
            if existing:
                return existing

        va = VirtualAccount.objects.select_for_update().get(pk=virtual_account.pk)
        if entry_type == VaLedgerEntry.EntryType.CREDIT:
            va.ledger_balance += amount
        elif entry_type == VaLedgerEntry.EntryType.DEBIT:
            if va.ledger_balance < amount:
                raise BusinessException(ErrorCode.INSUFFICIENT_BALANCE, "The virtual account has insufficient available balance")
            va.ledger_balance -= amount
        else:
            raise BusinessException("LEDGER_TYPE_INVALID", "The ledger entry direction is unknown")

        if not va.is_frozen:
            va.available_balance = va.ledger_balance
        va.save(update_fields=["ledger_balance", "available_balance", "updated_at"])

        if update_master and va.master_account_id:
            master = NostroAccount.objects.select_for_update().get(pk=va.master_account_id)
            if entry_type == VaLedgerEntry.EntryType.CREDIT:
                master.balance += amount
            else:
                if master.balance < amount:
                    raise BusinessException(ErrorCode.INSUFFICIENT_BALANCE, "The parent account has insufficient available balance")
                master.balance -= amount
            master.save(update_fields=["balance", "updated_at"])

        return VaLedgerEntry.objects.create(
            virtual_account=va,
            order=order,
            entry_type=entry_type,
            amount=amount,
            balance_after=va.ledger_balance,
            source_type=source_type,
            source_id=src_id,
            remark=remark,
        )

    @staticmethod
    def generate_deposit_no() -> str:
        import datetime
        return f"D{datetime.date.today().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"

    @staticmethod
    def parse_deposit_amount(value) -> Decimal:
        from decimal import InvalidOperation, ROUND_HALF_UP

        try:
            amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError):
            raise BusinessException("PARAM_INVALID", "The amount is not a valid figure")
        if amount <= 0:
            raise BusinessException("PARAM_INVALID", "The amount must be a positive figure")
        return amount

    def _merchant_currency_va(self, merchant, currency: str) -> VirtualAccount | None:
        from apps.merchant.services import ensure_merchant_currency_account

        ensure_merchant_currency_account(merchant, currency)
        qs = VirtualAccount.objects.filter(
            merchant=merchant,
            currency=currency,
            status=VirtualAccount.VaStatus.ACTIVE,
            is_deleted=False,
        )
        preferred = qs.filter(va_type=VirtualAccount.VaType.VAV).first()
        return preferred or qs.first()

    def merchant_va_for_currency(self, merchant, currency: str) -> VirtualAccount | None:
        ccy = (currency or "").strip().upper() or "CNY"
        return self._merchant_currency_va(merchant, ccy)

    def debit_va_for_order_outflow(self, order, *, remark: str = "") -> VaLedgerEntry | None:
        """Debit the VA that was credited on collection. Idempotent on SETTLEMENT + order id."""
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
        va = credit.virtual_account if credit else None
        amount = credit.amount if credit else order.amount
        if not va:
            currency = (
                order.from_currency or order.currency or order.to_currency or "CNY"
            )
            va = self.merchant_va_for_currency(order.merchant, currency)
        if not va or not amount or amount <= 0:
            return None
        note = remark or f"Confirm transfer {order.order_no}"
        entry = self.post_va_entry(
            virtual_account=va,
            amount=amount,
            entry_type=VaLedgerEntry.EntryType.DEBIT,
            order=order,
            remark=note,
            source_type="SETTLEMENT",
            source_id=str(order.id),
        )
        self.debit_agent_pool_for_outflow(
            merchant=order.merchant,
            amount=amount,
            currency=va.currency or order.from_currency or order.currency or "CNY",
            origin_source="SETTLEMENT",
            origin_id=str(order.id),
            remark=note,
        )
        return entry

    def _agent_current_va(self, agent, currency: str) -> VirtualAccount | None:
        from apps.agent.services import ensure_agent_accounts, get_agent_ledger_va

        ensure_agent_accounts(agent, currency)
        return get_agent_ledger_va(agent, NostroAccount.AccountType.CURRENT, currency)

    def create_agent_self_deposit(self, *, agent, currency: str, amount, remark: str = "") -> DepositRequest:
        from apps.agent.services import ensure_agent_accounts, get_agent_account
        from apps.core.currencies import is_supported_currency, normalize_currency

        currency = normalize_currency(currency)
        if not is_supported_currency(currency):
            raise BusinessException("INVALID_CURRENCY", "The currency is not a supported ISO 4217 code")
        amount = self.parse_deposit_amount(amount)
        ensure_agent_accounts(agent, currency)
        master = get_agent_account(agent, NostroAccount.AccountType.CURRENT, currency)
        if not master:
            raise BusinessException("ACCOUNT_NOT_FOUND", "The agent currency pool does not exist")
        return DepositRequest.objects.create(
            deposit_no=self.generate_deposit_no(),
            merchant=None,
            agent=agent,
            account=master,
            source=DepositRequest.DepositSource.AGENT_SELF,
            currency=currency,
            amount=amount,
            remark=(remark or "").strip()[:256],
            status=DepositRequest.DepositStatus.PENDING,
        )

    def create_customer_deposit(self, *, merchant, currency: str, amount, remark: str = "") -> DepositRequest:
        from apps.core.currencies import is_supported_currency, normalize_currency
        from apps.merchant.services import ensure_merchant_currency_account

        currency = normalize_currency(currency)
        if not is_supported_currency(currency):
            raise BusinessException("INVALID_CURRENCY", "The currency is not a supported ISO 4217 code")
        amount = self.parse_deposit_amount(amount)
        ensure_merchant_currency_account(merchant, currency)
        master = merchant.nostro_accounts.filter(is_deleted=False, currency=currency).first()
        agent = getattr(merchant, "agent", None)
        return DepositRequest.objects.create(
            deposit_no=self.generate_deposit_no(),
            merchant=merchant,
            agent=agent,
            account=master,
            source=DepositRequest.DepositSource.CUSTOMER,
            currency=currency,
            amount=amount,
            remark=(remark or "").strip()[:256],
            status=DepositRequest.DepositStatus.PENDING,
        )

    def _credit_agent_current(
        self, *, agent, amount: Decimal, currency: str, source_type: str, source_id: str, remark: str,
    ) -> VaLedgerEntry | None:
        va = self._agent_current_va(agent, currency)
        if not va:
            return None
        return self.post_va_entry(
            virtual_account=va,
            amount=amount,
            entry_type=VaLedgerEntry.EntryType.CREDIT,
            remark=remark,
            source_type=source_type,
            source_id=source_id,
        )

    def debit_agent_pool_for_outflow(
        self,
        *,
        merchant,
        amount: Decimal,
        currency: str,
        origin_source: str,
        origin_id: str,
        remark: str = "",
    ) -> VaLedgerEntry | None:
        """No-op: agent has no operable book; customer VA is the sole ledger."""
        return None

    @transaction.atomic
    def approve_deposit(self, deposit: DepositRequest, *, reviewer: str = "", comment: str = "") -> DepositRequest:
        locked = DepositRequest.objects.select_for_update().select_related(
            "merchant", "agent", "account",
        ).get(pk=deposit.pk)
        if locked.status != DepositRequest.DepositStatus.PENDING:
            raise BusinessException(
                "DEPOSIT_STATUS_INVALID",
                f"The deposit request is in status {locked.status} and cannot be reviewed",
            )
        amount = locked.amount
        currency = (locked.currency or "").upper()
        remark = f"Deposit {locked.deposit_no}"
        source = locked.source or DepositRequest.DepositSource.CUSTOMER
        if source == DepositRequest.DepositSource.AGENT_SELF:
            if not locked.agent_id:
                raise BusinessException("PARAM_MISSING", "The agent is required for this deposit")
            # Legacy path retained for ops/tests; agent portal no longer creates AGENT_SELF.
            self._credit_agent_current(
                agent=locked.agent,
                amount=amount,
                currency=currency,
                source_type="DEPOSIT",
                source_id=str(locked.id),
                remark=remark,
            )
        else:
            if not locked.merchant_id:
                raise BusinessException("PARAM_MISSING", "The customer is required for this deposit")
            va = self._merchant_currency_va(locked.merchant, currency)
            if not va:
                raise BusinessException("ACCOUNT_NOT_FOUND", "The customer virtual account does not exist")
            self.post_va_entry(
                virtual_account=va,
                amount=amount,
                entry_type=VaLedgerEntry.EntryType.CREDIT,
                remark=remark,
                source_type="DEPOSIT",
                source_id=str(locked.id),
            )
            agent = locked.agent or getattr(locked.merchant, "agent", None)
            if agent and not locked.agent_id:
                locked.agent = agent
        locked.status = DepositRequest.DepositStatus.APPROVED
        locked.reviewed_by = reviewer or ""
        locked.reviewed_at = timezone.now()
        locked.review_comment = comment or ""
        locked.save(update_fields=[
            "status", "agent", "reviewed_by", "reviewed_at", "review_comment", "updated_at",
        ])
        return locked

    @transaction.atomic
    def reject_deposit(self, deposit: DepositRequest, *, reviewer: str = "", reason: str = "") -> DepositRequest:
        locked = DepositRequest.objects.select_for_update().get(pk=deposit.pk)
        if locked.status != DepositRequest.DepositStatus.PENDING:
            raise BusinessException(
                "DEPOSIT_STATUS_INVALID",
                f"The deposit request is in status {locked.status} and cannot be reviewed",
            )
        reason = (reason or "").strip()
        if not reason:
            raise BusinessException("PARAM_MISSING", "Grounds for rejection are required")
        locked.status = DepositRequest.DepositStatus.REJECTED
        locked.reviewed_by = reviewer or ""
        locked.reviewed_at = timezone.now()
        locked.review_comment = reason
        locked.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_comment", "updated_at"])
        return locked


class DisbursementService:
    """代理资金拨付服务 — 双授权状态机驱动。

    对外转账强制双重授权（两名审批人），授权链由 DisbursementApproval 逐笔记录可追溯。
    """

    @transaction.atomic
    def submit(
        self, *, agent, amount, currency, payee_bank_name, payee_account_no,
        payee_account_holder="", swift_code="", remark="", operator="",
    ) -> AgentDisbursement:
        """提交拨付申请，进入待一审。"""
        if not isinstance(amount, Decimal) or amount <= 0:
            raise BusinessException("DISBURSEMENT_AMOUNT_INVALID", "The disbursement amount must be a positive figure")
        disbursement = AgentDisbursement(
            disbursement_no=generate_batch_no("D"),
            agent=agent,
            currency=currency,
            amount=amount,
            payee_bank_name=payee_bank_name,
            payee_account_no=payee_account_no,
            payee_account_holder=payee_account_holder,
            swift_code=swift_code,
            remark=remark,
            status=AgentDisbursement.DisbursementStatus.PENDING_FIRST_APPROVAL,
        )
        disbursement.save()
        return disbursement

    @transaction.atomic
    def approve(self, disbursement, step, approver, comment: str = ""):
        """双授权审批：一审/二审依次通过，二审通过即完成授权。"""
        status = disbursement.status
        if step == DisbursementApproval.ApprovalStep.FIRST:
            if status != AgentDisbursement.DisbursementStatus.PENDING_FIRST_APPROVAL:
                raise BusinessException("DISBURSEMENT_STEP_INVALID", "The current status does not permit first-level authorisation")
            next_status = AgentDisbursement.DisbursementStatus.PENDING_SECOND_APPROVAL
        elif step == DisbursementApproval.ApprovalStep.SECOND:
            if status != AgentDisbursement.DisbursementStatus.PENDING_SECOND_APPROVAL:
                raise BusinessException("DISBURSEMENT_STEP_INVALID", "The current status does not permit second-level authorisation")
            first = disbursement.approvals.filter(
                step=DisbursementApproval.ApprovalStep.FIRST,
                action=DisbursementApproval.ApprovalAction.APPROVE,
            ).first()
            if first and first.approver and first.approver == approver:
                raise BusinessException("DISBURSEMENT_SAME_APPROVER", "First-level and second-level authorisation must be performed by different principals")
            next_status = AgentDisbursement.DisbursementStatus.APPROVED
        else:
            raise BusinessException("DISBURSEMENT_STEP_INVALID", "The authorisation step is unknown")

        DisbursementApproval.objects.create(
            disbursement=disbursement,
            step=step,
            approver=approver,
            action=DisbursementApproval.ApprovalAction.APPROVE,
            comment=comment,
        )
        disbursement.status = next_status
        if next_status == AgentDisbursement.DisbursementStatus.APPROVED:
            disbursement.approved_at = timezone.now()
        disbursement.save(update_fields=["status", "approved_at", "updated_at"])
        return disbursement

    @transaction.atomic
    def reject(self, disbursement, step, approver, comment: str = ""):
        """驳回：任一环节驳回即终止。"""
        DisbursementApproval.objects.create(
            disbursement=disbursement,
            step=step,
            approver=approver,
            action=DisbursementApproval.ApprovalAction.REJECT,
            comment=comment,
        )
        disbursement.status = AgentDisbursement.DisbursementStatus.REJECTED
        disbursement.save(update_fields=["status", "updated_at"])
        return disbursement

    @transaction.atomic
    def execute(self, disbursement):
        """执行拨付 — 通过银行网关出金。"""
        import logging
        from django.conf import settings
        from apps.payment.gateway import BankGatewayRouter

        logger = logging.getLogger(__name__)
        if disbursement.status != AgentDisbursement.DisbursementStatus.APPROVED:
            raise BusinessException("DISBURSEMENT_STATUS_INVALID", "Only an authorised disbursement instruction may be executed")

        from apps.agent.services import ensure_agent_accounts, get_agent_account, get_agent_ledger_va

        ensure_agent_accounts(disbursement.agent, disbursement.currency or "CNY")
        current = get_agent_account(
            disbursement.agent, NostroAccount.AccountType.CURRENT, disbursement.currency
        )
        if not current or current.balance < disbursement.amount:
            raise BusinessException(ErrorCode.INSUFFICIENT_BALANCE, "The agent current account has insufficient available balance")

        disbursement.status = AgentDisbursement.DisbursementStatus.EXECUTING
        disbursement.save(update_fields=["status", "updated_at"])
        try:
            gateway = BankGatewayRouter.get_gateway(current.bank_code)
            logger.info(
                "disbursement.execute start no=%s amount=%s",
                disbursement.disbursement_no, disbursement.amount,
            )
            result = gateway.disburse(
                payee_bank_name=disbursement.payee_bank_name or "",
                payee_account_no=disbursement.payee_account_no,
                payee_account_holder=disbursement.payee_account_holder or "",
                amount=disbursement.amount,
                currency=disbursement.currency,
                disbursement_no=disbursement.disbursement_no,
                swift_code=getattr(disbursement, "swift_code", "") or "",
                remark=disbursement.remark or "",
            )
            if not result.get("success"):
                raise BusinessException(
                    "DISBURSEMENT_BANK_FAILED",
                    result.get("message", "The bank payout could not be completed"),
                )
            disbursement.status = AgentDisbursement.DisbursementStatus.SUCCESS
            disbursement.executed_at = timezone.now()
            disbursement.save(update_fields=["status", "executed_at", "updated_at"])
            va = get_agent_ledger_va(
                disbursement.agent, NostroAccount.AccountType.CURRENT, disbursement.currency
            )
            if va:
                AccountService().post_va_entry(
                    virtual_account=va,
                    amount=disbursement.amount,
                    entry_type=VaLedgerEntry.EntryType.DEBIT,
                    remark=f"代理拨付 {disbursement.disbursement_no}",
                    source_type="DISBURSEMENT",
                    source_id=str(disbursement.id),
                )
        except NotImplementedError as exc:
            disbursement.status = AgentDisbursement.DisbursementStatus.FAILED
            disbursement.fail_reason = str(exc)[:256]
            disbursement.save(update_fields=["status", "fail_reason", "updated_at"])
            raise BusinessException("DISBURSEMENT_NOT_CONFIGURED", str(exc))
        except BusinessException:
            if disbursement.status == AgentDisbursement.DisbursementStatus.EXECUTING:
                disbursement.status = AgentDisbursement.DisbursementStatus.FAILED
                disbursement.fail_reason = "The bank payout could not be completed"
                disbursement.save(update_fields=["status", "fail_reason", "updated_at"])
            raise
        except Exception as exc:  # noqa: BLE001
            disbursement.status = AgentDisbursement.DisbursementStatus.FAILED
            disbursement.fail_reason = str(exc)[:256]
            disbursement.save(update_fields=["status", "fail_reason", "updated_at"])
            raise
        return disbursement


def parse_page_params(page, page_size, default_size=20, max_size=100):
    try:
        page = max(int(page or 1), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(max(int(page_size or default_size), 1), max_size)
    except (TypeError, ValueError):
        page_size = default_size
    return page, page_size


def apply_virtual_account_list_filters(qs, *, search="", status=""):
    from django.db import models as db_models

    qs = qs.filter(is_deleted=False, merchant_id__isnull=False)
    if status:
        qs = qs.filter(status=status)
    search = (search or "").strip()
    if search:
        qs = qs.filter(
            db_models.Q(va_number__icontains=search)
            | db_models.Q(reference__icontains=search)
            | db_models.Q(label__icontains=search)
            | db_models.Q(merchant__merchant_name__icontains=search)
            | db_models.Q(merchant__merchant_no__icontains=search)
        )
    return qs


def group_virtual_accounts_by_customer(matched_qs, *, page=1, page_size=20):
    """一行一个 Customer；详情含该客户全部未删除 VA。"""
    from collections import defaultdict
    from decimal import Decimal

    from .serializers import VirtualAccountSerializer

    merchant_ids = list(dict.fromkeys(
        matched_qs.order_by("merchant__merchant_name", "merchant_id")
        .values_list("merchant_id", flat=True)
    ))
    total = len(merchant_ids)
    start = (page - 1) * page_size
    page_ids = merchant_ids[start:start + page_size]
    accounts = (
        VirtualAccount.objects.filter(is_deleted=False, merchant_id__in=page_ids)
        .select_related("master_account", "merchant", "agent", "order")
        .order_by("currency", "va_number")
    )
    grouped = {}
    for va in accounts:
        grouped.setdefault(va.merchant_id, []).append(va)

    currency_rank = {"CNY": 0, "USD": 1, "EUR": 2, "HKD": 3}
    status_rank = (
        VirtualAccount.VaStatus.ACTIVE,
        VirtualAccount.VaStatus.FROZEN,
        VirtualAccount.VaStatus.INACTIVE,
        VirtualAccount.VaStatus.REVOKED,
    )
    results = []
    for merchant_id in page_ids:
        vas = grouped.get(merchant_id) or []
        if not vas:
            continue
        merchant = vas[0].merchant
        statuses = {va.status for va in vas}
        status_value = next((s for s in status_rank if s in statuses), vas[0].status)
        currencies = sorted(
            {va.currency for va in vas if va.currency},
            key=lambda ccy: (currency_rank.get(ccy, 99), ccy),
        )
        avail_by_ccy = defaultdict(lambda: Decimal("0"))
        ledger_by_ccy = defaultdict(lambda: Decimal("0"))
        for va in vas:
            ccy = (va.currency or "").upper()
            if not ccy:
                continue
            avail_by_ccy[ccy] += va.available_balance or Decimal("0")
            ledger_by_ccy[ccy] += va.ledger_balance or Decimal("0")
        totals = [
            {
                "currency": ccy,
                "available_balance": f"{avail_by_ccy[ccy]:.2f}",
                "ledger_balance": f"{ledger_by_ccy[ccy]:.2f}",
            }
            for ccy in currencies
        ]
        results.append({
            "merchant": str(merchant.id),
            "merchant_name": merchant.merchant_name,
            "merchant_no": merchant.merchant_no,
            "va_count": len(vas),
            "currencies": currencies,
            "status": status_value,
            "totals": totals,
            "accounts": VirtualAccountSerializer(vas, many=True).data,
        })
    return {"count": total, "results": results}


def virtual_account_status_stats(qs):
    from django.db.models import Count

    qs = qs.filter(is_deleted=False)
    status_counts = dict(qs.values_list("status").annotate(cnt=Count("id")))
    return {
        "total": qs.count(),
        "active": status_counts.get("ACTIVE", 0),
        "inactive": status_counts.get("INACTIVE", 0),
        "revoked": status_counts.get("REVOKED", 0),
    }


def serialize_virtual_account_transactions(va):
    from apps.account.views import build_account_transactions

    entries = va.ledger_entries.filter(is_deleted=False).order_by("-created_at")
    if entries.exists():
        txns = [
            {
                "id": str(e.id),
                "type": e.entry_type,
                "type_class": "credit" if e.entry_type == "CREDIT" else "debit",
                "direction": "in" if e.entry_type == "CREDIT" else "out",
                "amount": str(e.amount) if e.entry_type == "CREDIT" else f"-{e.amount}",
                "currency": va.currency,
                "status": "POSTED",
                "status_label": "Posted",
                "ref_no": e.source_id or (e.order.order_no if e.order_id else ""),
                "remark": e.remark or "",
                "created_at": str(e.created_at),
                "balance_after": str(e.balance_after),
            }
            for e in entries
        ]
        return {
            "va_number": va.va_number,
            "currency": va.currency,
            "balance": str(va.ledger_balance),
            "available_balance": str(va.available_balance),
            "transactions": txns,
            "count": len(txns),
        }
    master = va.master_account
    if not master:
        return {
            "va_number": va.va_number,
            "currency": va.currency,
            "balance": str(va.ledger_balance),
            "transactions": [],
            "count": 0,
        }
    txns = build_account_transactions(master)
    return {
        "va_number": va.va_number,
        "account_no": master.account_no,
        "bank_name": master.bank_name,
        "currency": va.currency or master.currency,
        "balance": str(va.ledger_balance),
        "transactions": txns,
        "count": len(txns),
    }
