"""账户体系 — 业务服务层。"""
from __future__ import annotations
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.core.exceptions import BusinessException, ErrorCode
from apps.core.utils import generate_batch_no, encrypt_field, decrypt_field
from .models import (
    NostroAccount, UserAccount, FundTransfer, UserPaymentDetail,
    AgentDisbursement, DisbursementApproval,
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
            bind_token=encrypt_field(bind_token),
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
            raise BusinessException("TRANSFER_SAME_ACCOUNT", "不能在同一账户之间调拨")

        transfer = FundTransfer(
            transfer_no=generate_batch_no("T"),
            from_account=from_account,
            to_account=to_account,
            amount=amount,
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
            raise BusinessException("DISBURSEMENT_AMOUNT_INVALID", "拨付金额必须为正数")
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
                raise BusinessException("DISBURSEMENT_STEP_INVALID", "当前状态不可进行一审")
            next_status = AgentDisbursement.DisbursementStatus.PENDING_SECOND_APPROVAL
        elif step == DisbursementApproval.ApprovalStep.SECOND:
            if status != AgentDisbursement.DisbursementStatus.PENDING_SECOND_APPROVAL:
                raise BusinessException("DISBURSEMENT_STEP_INVALID", "当前状态不可进行二审")
            next_status = AgentDisbursement.DisbursementStatus.APPROVED
        else:
            raise BusinessException("DISBURSEMENT_STEP_INVALID", "未知的审批环节")

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
            raise BusinessException("DISBURSEMENT_STATUS_INVALID", "仅已授权的拨付单可执行")
        disbursement.status = AgentDisbursement.DisbursementStatus.EXECUTING
        disbursement.save(update_fields=["status", "updated_at"])
        try:
            bank_code = settings.BANK_CODES[0] if settings.BANK_CODES else "MOCK"
            gateway = BankGatewayRouter.get_gateway(bank_code)
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
                    result.get("message", "银行出金失败"),
                )
            disbursement.status = AgentDisbursement.DisbursementStatus.SUCCESS
            disbursement.executed_at = timezone.now()
            disbursement.save(update_fields=["status", "executed_at", "updated_at"])
        except NotImplementedError as exc:
            disbursement.status = AgentDisbursement.DisbursementStatus.FAILED
            disbursement.fail_reason = str(exc)[:256]
            disbursement.save(update_fields=["status", "fail_reason", "updated_at"])
            raise BusinessException("DISBURSEMENT_NOT_CONFIGURED", str(exc))
        except BusinessException:
            if disbursement.status == AgentDisbursement.DisbursementStatus.EXECUTING:
                disbursement.status = AgentDisbursement.DisbursementStatus.FAILED
                disbursement.fail_reason = "银行出金失败"
                disbursement.save(update_fields=["status", "fail_reason", "updated_at"])
            raise
        except Exception as exc:  # noqa: BLE001
            disbursement.status = AgentDisbursement.DisbursementStatus.FAILED
            disbursement.fail_reason = str(exc)[:256]
            disbursement.save(update_fields=["status", "fail_reason", "updated_at"])
            raise
        return disbursement
