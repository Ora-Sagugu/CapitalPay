"""账户体系 — 模型定义。

包含: NostroAccount (我司在他行账户)、UserAccount (用户账户绑定)、FundTransfer (资金调拨)。
"""
from decimal import Decimal
import uuid
from django.db import models
from django.utils import timezone
from apps.core.models import BaseModel


class NostroAccount(BaseModel):
    """Nostro 账户 — 支付公司在他行的账户。

    用于接收用户汇款、向商户结算、资金调拨。
    """

    class AccountType(models.TextChoices):
        SETTLEMENT = "SETTLEMENT", "结算账户"
        COLLECTION = "COLLECTION", "收款账户"
        RESERVE = "RESERVE", "备付金账户"
        CURRENT = "CURRENT", "往来账户"
        FEE = "FEE", "手续费账户"

    account_no = models.CharField(max_length=32, unique=True, verbose_name="账户编号")
    bank_code = models.CharField(max_length=16, verbose_name="银行编码")
    bank_name = models.CharField(max_length=128, verbose_name="银行名称")
    account_number = models.CharField(max_length=256, verbose_name="账号(加密)")
    account_type = models.CharField(
        max_length=16, choices=AccountType.choices, default=AccountType.COLLECTION, verbose_name="账户类型"
    )
    currency = models.CharField(max_length=3, default="CNY", verbose_name="币种")
    balance = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="账面余额"
    )
    last_reconciled_balance = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, verbose_name="最后对账余额"
    )
    last_reconciled_at = models.DateTimeField(null=True, verbose_name="最后对账时间")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    max_single_amount = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True, verbose_name="单笔限额"
    )
    daily_limit = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True, verbose_name="单日限额"
    )
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="注销时间")
    close_reason = models.CharField(max_length=256, blank=True, verbose_name="注销原因")
    merchant = models.ForeignKey(
        "merchant.Merchant", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="nostro_accounts", verbose_name="关联客户"
    )
    agent = models.ForeignKey(
        "agent.Agent", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="nostro_accounts", verbose_name="关联代理商"
    )

    class Meta:
        db_table = "nostro_account"
        verbose_name = "Nostro账户"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.bank_name} - {self.account_no}"

    @property
    def virtual_accounts_total(self):
        """子账户(VA)余额合计 — 用于与账面余额对账(账实分离)。"""
        from django.db.models import Sum
        total = self.virtual_accounts.filter(
            status=VirtualAccount.VaStatus.ACTIVE
        ).aggregate(s=Sum("ledger_balance"))["s"]
        return total or 0

    @property
    def virtual_accounts_count(self):
        """子账户(VA)数量。"""
        return self.virtual_accounts.filter(status=VirtualAccount.VaStatus.ACTIVE).count()


class UserAccount(BaseModel):
    """用户账户 — 用户在平台的账户绑定记录。

    功能清单对应:
        - 用户账户绑定 (与银行账户平台对接，在线银行账户绑定授权支付)
    """

    class BindStatus(models.TextChoices):
        PENDING = "PENDING", "待验证"
        ACTIVE = "ACTIVE", "已绑定"
        EXPIRED = "EXPIRED", "已过期"
        REVOKED = "REVOKED", "已解绑"

    user_id = models.CharField(max_length=64, db_index=True, verbose_name="用户ID")
    merchant = models.ForeignKey(
        "merchant.Merchant", on_delete=models.PROTECT, verbose_name="所属商户"
    )
    bank_code = models.CharField(max_length=16, verbose_name="银行编码")
    bank_name = models.CharField(max_length=128, verbose_name="银行名称")
    account_holder = models.CharField(max_length=64, verbose_name="账户持有人")
    account_number = models.CharField(max_length=256, verbose_name="账号(加密)")
    bind_token = models.CharField(max_length=256, verbose_name="绑定Token(加密)")
    status = models.CharField(
        max_length=16, choices=BindStatus.choices, default=BindStatus.PENDING, verbose_name="状态"
    )
    bind_at = models.DateTimeField(null=True, verbose_name="绑定时间")
    expire_at = models.DateTimeField(null=True, verbose_name="授权过期时间")

    class Meta:
        db_table = "user_account"
        verbose_name = "用户账户"
        verbose_name_plural = verbose_name
        unique_together = [["user_id", "bank_code", "account_number"]]


class FundTransfer(BaseModel):
    """资金调拨记录 — nostro 账户之间的资金划转。

    功能清单对应:
        - nostro账户资金调拨
    """

    class TransferStatus(models.TextChoices):
        PENDING = "PENDING", "待执行"
        PROCESSING = "PROCESSING", "执行中"
        SUCCESS = "SUCCESS", "已到账"
        FAILED = "FAILED", "失败"

    transfer_no = models.CharField(max_length=32, unique=True, verbose_name="调拨单号")
    from_account = models.ForeignKey(
        NostroAccount, on_delete=models.PROTECT, related_name="out_transfers", verbose_name="调出账户"
    )
    to_account = models.ForeignKey(
        NostroAccount, on_delete=models.PROTECT, related_name="in_transfers", verbose_name="调入账户"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="调拨金额")
    currency = models.CharField(max_length=3, default="CNY", verbose_name="币种")
    status = models.CharField(
        max_length=16, choices=TransferStatus.choices, default=TransferStatus.PENDING, verbose_name="状态"
    )
    remark = models.CharField(max_length=256, blank=True, verbose_name="备注")
    executed_at = models.DateTimeField(null=True, verbose_name="执行时间")

    class Meta:
        db_table = "fund_transfer"
        verbose_name = "资金调拨"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]


class UserPaymentDetail(BaseModel):
    """用户支付明细。

    功能清单对应:
        - 用户支付明细
    """

    user_id = models.CharField(max_length=64, db_index=True, verbose_name="用户ID")
    order = models.OneToOneField(
        "payment.PaymentOrder", on_delete=models.PROTECT, verbose_name="支付订单"
    )
    account = models.ForeignKey(
        UserAccount, on_delete=models.PROTECT, null=True, verbose_name="支付账户"
    )
    pay_method = models.CharField(max_length=32, verbose_name="支付方式")
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="支付金额")
    pay_time = models.DateTimeField(verbose_name="支付时间")

    class Meta:
        db_table = "user_payment_detail"
        verbose_name = "用户支付明细"
        verbose_name_plural = verbose_name


class DepositRequest(BaseModel):
    """存款/入账请求 — 客户或运营提交存款，运营审核后到账。

    功能清单对应:
        - Transfer Management (存款管理) 2.4.4
    """

    class DepositStatus(models.TextChoices):
        PENDING = "PENDING", "待审核"
        APPROVED = "APPROVED", "已通过"
        REJECTED = "REJECTED", "已拒绝"

    class DepositSource(models.TextChoices):
        CUSTOMER = "CUSTOMER", "客户充值"
        AGENT_SELF = "AGENT_SELF", "代理自充"

    deposit_no = models.CharField(max_length=32, unique=True, db_index=True, verbose_name="入账单号")
    merchant = models.ForeignKey(
        "merchant.Merchant", on_delete=models.PROTECT, null=True, blank=True,
        related_name="deposits", verbose_name="客户"
    )
    agent = models.ForeignKey(
        "agent.Agent", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="deposits", verbose_name="代理商"
    )
    source = models.CharField(
        max_length=16, choices=DepositSource.choices, default=DepositSource.CUSTOMER,
        verbose_name="来源",
    )
    account = models.ForeignKey(
        NostroAccount, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="deposits", verbose_name="入账账户"
    )
    currency = models.CharField(max_length=3, default="USD", verbose_name="币种")
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="入账金额")
    status = models.CharField(
        max_length=16, choices=DepositStatus.choices, default=DepositStatus.PENDING, verbose_name="状态"
    )
    remark = models.CharField(max_length=256, blank=True, verbose_name="备注")
    reviewed_by = models.CharField(max_length=64, null=True, blank=True, verbose_name="审核人")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="审核时间")
    review_comment = models.CharField(max_length=256, blank=True, verbose_name="审核意见")

    class Meta:
        db_table = "deposit_request"
        verbose_name = "存款请求"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["merchant", "status"]),
            models.Index(fields=["agent", "status"]),
            models.Index(fields=["currency", "status"]),
        ]

    def __str__(self):
        return f"{self.deposit_no} - {self.amount} {self.currency}"


class VirtualAccount(BaseModel):
    """虚拟账户 (Virtual Account) — 伞形母账户下的逻辑分账子账号。

    底层逻辑: 在银行/支付机构的实体「伞形母账户」(NostroAccount) 下，通过系统映射
    生成多个独立虚拟子账号，利用「账实分离」机制实现资金流与信息流的解耦，以低成本
    本地清算通道完成跨境收款的自动化识别与归集。

    两类主要形态:
        - VLA (Virtual Ledger Account): 纯内部分类账记录，无对外银行账号形式。
        - VAV (Virtual Bank Account Number): 对外提供看似真实银行账号(含本地路由码/IBAN)，
          是跨境收款的主流形态。

    关键特征:
        - 非实体性: 无独立银行牌照资金支持，不能提现/透支。
        - 账实分离: 余额由关联母账户派生，VA 本身不存真实资金。
        - 一笔一码: 可绑定特定商户、订单或业务场景，用于自动化对账。
    """

    class VaType(models.TextChoices):
        VLA = "VLA", "Virtual Ledger Account"
        VAV = "VAV", "Virtual Bank Account Number"

    class VaStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "启用"
        INACTIVE = "INACTIVE", "停用"
        FROZEN = "FROZEN", "冻结"
        REVOKED = "REVOKED", "已注销"

    class ClearingNetwork(models.TextChoices):
        ACH = "ACH", "ACH (美国)"
        SEPA = "SEPA", "SEPA (欧元区)"
        SEPA_INST = "SEPA_INST", "SEPA 即时"
        FPS = "FPS", "FPS (香港)"
        FAST = "FAST", "FAST (新加坡)"
        CHAPS = "CHAPS", "CHAPS (英国)"
        BACS = "BACS", "BACS (英国)"
        SWIFT = "SWIFT", "SWIFT (跨境电汇)"
        PIX = "PIX", "PIX (巴西)"
        OTHER = "OTHER", "其他"

    master_account = models.ForeignKey(
        NostroAccount, on_delete=models.PROTECT, related_name="virtual_accounts",
        verbose_name="母账户(伞形实体账户)",
    )
    merchant = models.ForeignKey(
        "merchant.Merchant", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="virtual_accounts", verbose_name="关联客户",
    )
    agent = models.ForeignKey(
        "agent.Agent", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="virtual_accounts", verbose_name="关联代理商",
    )
    order = models.ForeignKey(
        "payment.PaymentOrder", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="virtual_accounts", verbose_name="关联订单(一笔一码)",
    )
    va_number = models.CharField(max_length=64, unique=True, db_index=True, verbose_name="虚拟账号")
    va_type = models.CharField(
        max_length=8, choices=VaType.choices, default=VaType.VAV, verbose_name="虚拟账户类型"
    )
    label = models.CharField(max_length=128, blank=True, verbose_name="虚拟账户名称")
    reference = models.CharField(max_length=64, blank=True, verbose_name="业务参考号(订单号/商户号)")
    bank_code = models.CharField(max_length=16, verbose_name="银行编码")
    bank_name = models.CharField(max_length=128, verbose_name="银行名称")
    account_holder = models.CharField(max_length=128, verbose_name="账户持有人")
    routing_code = models.CharField(max_length=32, blank=True, verbose_name="本地路由码")
    clearing_network = models.CharField(
        max_length=16, blank=True, choices=ClearingNetwork.choices,
        verbose_name="本地清算网络(ACH/SEPA/FPS)",
    )
    country = models.CharField(max_length=2, blank=True, verbose_name="国家(ISO2)")
    currency = models.CharField(max_length=3, default="CNY", verbose_name="币种")
    # 分类账余额 — VA 自身的余额(账实分离下的子账户余额)，与母账户对账相等
    ledger_balance = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="分类账余额"
    )
    available_balance = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="可用余额"
    )
    status = models.CharField(
        max_length=16, choices=VaStatus.choices, default=VaStatus.ACTIVE, verbose_name="状态"
    )
    opened_at = models.DateTimeField(null=True, blank=True, verbose_name="开通时间")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="注销时间")
    close_reason = models.CharField(max_length=256, blank=True, verbose_name="注销原因")
    freeze_reason = models.CharField(max_length=256, blank=True, verbose_name="冻结原因")
    frozen_at = models.DateTimeField(null=True, blank=True, verbose_name="冻结时间")

    class Meta:
        db_table = "virtual_account"
        verbose_name = "虚拟账户"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["merchant", "va_type", "status"]),
            models.Index(fields=["agent", "va_type", "status"]),
            models.Index(fields=["order"]),
        ]

    def __str__(self):
        return f"{self.va_number} ({self.get_va_type_display()})"

    @property
    def balance(self):
        """余额 — VA 自身的分类账余额(账实分离下的子账户余额)。"""
        return self.ledger_balance

    @property
    def is_frozen(self) -> bool:
        """是否处于冻结状态。"""
        return self.status == self.VaStatus.FROZEN

    def freeze(self, reason: str = "", operator: str = ""):
        """冻结虚拟账户 — 可用余额置 0，状态置 FROZEN。"""
        self.status = self.VaStatus.FROZEN
        self.available_balance = Decimal("0")
        self.freeze_reason = reason
        self.frozen_at = timezone.now()
        self.save(update_fields=["status", "available_balance", "freeze_reason", "frozen_at", "updated_at"])

    def unfreeze(self, operator: str = ""):
        """解冻 — 恢复可用余额=分类账余额，状态置 ACTIVE。"""
        self.status = self.VaStatus.ACTIVE
        self.available_balance = self.ledger_balance
        self.freeze_reason = ""
        self.frozen_at = None
        self.save(update_fields=["status", "available_balance", "freeze_reason", "frozen_at", "updated_at"])

    def sync_available_balance(self):
        """同步可用余额：冻结时为 0，否则等于分类账余额。"""
        self.available_balance = Decimal("0") if self.is_frozen else self.ledger_balance
        self.save(update_fields=["available_balance", "updated_at"])


class MoneyMovement(models.Model):
    """不可变资金流水 — 收款、出款、退款、分润冲正的账务事实。

    仅允许插入，禁止 update/delete。同一来源幂等：
    (source_type, source_id, movement_type) 唯一。
    """

    class MovementType(models.TextChoices):
        COLLECTION = "COLLECTION", "系统确认收款"
        SETTLEMENT_PAYOUT = "SETTLEMENT_PAYOUT", "清算出款"
        REFUND = "REFUND", "退款"
        FEE_SHARE = "FEE_SHARE", "手续费分润"
        REVERSAL = "REVERSAL", "冲正"

    class MovementStatus(models.TextChoices):
        PENDING = "PENDING", "处理中"
        SUCCESS = "SUCCESS", "成功"
        FAILED = "FAILED", "失败"

    class EvidenceLevel(models.TextChoices):
        UNVERIFIED = "UNVERIFIED", "尚未证实"
        SYSTEM_CONFIRMED = "SYSTEM_CONFIRMED", "系统确认"
        BANK_CONFIRMED = "BANK_CONFIRMED", "银行凭证"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    movement_no = models.CharField(max_length=40, unique=True, db_index=True, verbose_name="流水号")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")
    occurred_at = models.DateTimeField(db_index=True, verbose_name="发生时间")
    movement_type = models.CharField(max_length=24, choices=MovementType.choices, verbose_name="类型")
    status = models.CharField(
        max_length=16, choices=MovementStatus.choices, default=MovementStatus.SUCCESS, verbose_name="状态"
    )
    evidence_level = models.CharField(
        max_length=24, choices=EvidenceLevel.choices, default=EvidenceLevel.SYSTEM_CONFIRMED,
        verbose_name="证据等级",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="金额")
    currency = models.CharField(max_length=3, verbose_name="币种")
    from_party_type = models.CharField(max_length=32, blank=True, default="", verbose_name="付款方类型")
    from_party_id = models.CharField(max_length=64, blank=True, default="", verbose_name="付款方ID")
    from_account = models.CharField(max_length=128, blank=True, default="", verbose_name="付款账号")
    to_party_type = models.CharField(max_length=32, blank=True, default="", verbose_name="收款方类型")
    to_party_id = models.CharField(max_length=64, blank=True, default="", verbose_name="收款方ID")
    to_account = models.CharField(max_length=128, blank=True, default="", verbose_name="收款账号")
    bank_code = models.CharField(max_length=16, blank=True, default="", verbose_name="银行编码")
    bank_txn_id = models.CharField(max_length=64, blank=True, default="", verbose_name="银行流水号")
    source_type = models.CharField(max_length=32, db_index=True, verbose_name="来源类型")
    source_id = models.CharField(max_length=64, db_index=True, verbose_name="来源ID")
    payment_order = models.ForeignKey(
        "payment.PaymentOrder", on_delete=models.PROTECT, null=True, blank=True,
        related_name="money_movements", verbose_name="支付订单",
    )
    settlement_batch = models.ForeignKey(
        "settlement.SettlementBatch", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="money_movements", verbose_name="清算批次",
    )
    refund_order = models.ForeignKey(
        "payment.RefundOrder", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="money_movements", verbose_name="退款单",
    )
    remark = models.CharField(max_length=256, blank=True, default="", verbose_name="备注")
    extra = models.JSONField(default=dict, blank=True, verbose_name="附加信息")

    class Meta:
        db_table = "money_movement"
        verbose_name = "资金流水"
        verbose_name_plural = verbose_name
        ordering = ["-occurred_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "source_id", "movement_type"],
                name="uniq_money_movement_source",
            ),
        ]
        indexes = [
            models.Index(fields=["payment_order", "movement_type"]),
            models.Index(fields=["currency", "occurred_at"]),
            models.Index(fields=["status", "evidence_level"]),
        ]

    def __str__(self):
        return f"{self.movement_no} {self.movement_type} {self.amount} {self.currency}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("资金流水不可修改")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("资金流水不可删除")


class VaLedgerEntry(BaseModel):
    """虚拟账户分类账分录 — 收款确认、手续费、拨付等可追溯流水。"""

    class EntryType(models.TextChoices):
        CREDIT = "CREDIT", "贷记"
        DEBIT = "DEBIT", "借记"

    virtual_account = models.ForeignKey(
        VirtualAccount, on_delete=models.PROTECT, related_name="ledger_entries", verbose_name="虚拟账户"
    )
    order = models.ForeignKey(
        "payment.PaymentOrder", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="va_ledger_entries", verbose_name="关联订单",
    )
    entry_type = models.CharField(max_length=8, choices=EntryType.choices, verbose_name="方向")
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="金额")
    balance_after = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="记账后余额")
    source_type = models.CharField(max_length=32, default="PAYMENT", db_index=True, verbose_name="来源类型")
    source_id = models.CharField(max_length=64, blank=True, db_index=True, verbose_name="来源ID")
    remark = models.CharField(max_length=256, blank=True, verbose_name="摘要")

    class Meta:
        db_table = "va_ledger_entry"
        verbose_name = "VA分类账分录"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["source_type", "source_id", "entry_type"]),
        ]

    def __str__(self):
        return f"{self.entry_type} {self.amount} {self.virtual_account.va_number}"


class AgentDisbursement(BaseModel):
    """代理资金拨付单 — 对外转账，强制双重授权。

    状态机:
        PENDING_FIRST_APPROVAL → (一审通过) → PENDING_SECOND_APPROVAL
                              → (二审通过) → APPROVED → EXECUTING → SUCCESS / FAILED
        任一审批环节驳回 → REJECTED
    """

    class DisbursementStatus(models.TextChoices):
        PENDING_FIRST_APPROVAL = "PENDING_FIRST_APPROVAL", "待一审"
        PENDING_SECOND_APPROVAL = "PENDING_SECOND_APPROVAL", "待二审"
        APPROVED = "APPROVED", "已授权"
        EXECUTING = "EXECUTING", "执行中"
        SUCCESS = "SUCCESS", "拨付成功"
        FAILED = "FAILED", "拨付失败"
        REJECTED = "REJECTED", "已驳回"

    disbursement_no = models.CharField(max_length=32, unique=True, db_index=True, verbose_name="拨付单号")
    agent = models.ForeignKey(
        "agent.Agent", on_delete=models.PROTECT, related_name="disbursements", verbose_name="代理商"
    )
    currency = models.CharField(max_length=3, default="USD", verbose_name="币种")
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="拨付金额")
    payee_bank_name = models.CharField(max_length=128, verbose_name="收款银行")
    payee_account_no = models.CharField(max_length=64, verbose_name="收款账号")
    payee_account_holder = models.CharField(max_length=128, blank=True, verbose_name="收款账户持有人")
    swift_code = models.CharField(max_length=16, blank=True, verbose_name="SWIFT代码")
    remark = models.CharField(max_length=256, blank=True, verbose_name="备注")
    status = models.CharField(
        max_length=24, choices=DisbursementStatus.choices,
        default=DisbursementStatus.PENDING_FIRST_APPROVAL, verbose_name="状态",
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="授权完成时间")
    executed_at = models.DateTimeField(null=True, blank=True, verbose_name="执行时间")
    fail_reason = models.CharField(max_length=256, blank=True, verbose_name="失败原因")
    notify_status = models.CharField(max_length=16, default="PENDING", verbose_name="通知状态")

    class Meta:
        db_table = "agent_disbursement"
        verbose_name = "代理资金拨付"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.disbursement_no} - {self.amount} {self.currency}"


class DisbursementApproval(BaseModel):
    """拨付审批记录 — 双授权链，逐笔可追溯。"""

    class ApprovalStep(models.TextChoices):
        FIRST = "FIRST", "一审"
        SECOND = "SECOND", "二审"

    class ApprovalAction(models.TextChoices):
        APPROVE = "APPROVE", "通过"
        REJECT = "REJECT", "驳回"

    disbursement = models.ForeignKey(
        AgentDisbursement, on_delete=models.CASCADE, related_name="approvals", verbose_name="拨付单"
    )
    step = models.CharField(max_length=8, choices=ApprovalStep.choices, verbose_name="审批环节")
    approver = models.CharField(max_length=64, verbose_name="审批人")
    action = models.CharField(max_length=8, choices=ApprovalAction.choices, verbose_name="审批动作")
    comment = models.CharField(max_length=256, blank=True, verbose_name="审批意见")
    approved_at = models.DateTimeField(auto_now_add=True, verbose_name="审批时间")

    class Meta:
        db_table = "disbursement_approval"
        verbose_name = "拨付审批记录"
        verbose_name_plural = verbose_name
        ordering = ["created_at"]


class AgentDisbursementSchedule(BaseModel):
    """代理自动拨付计划 — 按预设频度/阈值自动发起拨付。"""

    class Frequency(models.TextChoices):
        DAILY = "DAILY", "每日"
        WEEKLY = "WEEKLY", "每周"
        MONTHLY = "MONTHLY", "每月"

    agent = models.OneToOneField(
        "agent.Agent", on_delete=models.CASCADE,
        related_name="disbursement_schedule", verbose_name="代理商"
    )
    enabled = models.BooleanField(default=False, verbose_name="是否启用自动拨付")
    frequency = models.CharField(max_length=8, choices=Frequency.choices, default=Frequency.MONTHLY, verbose_name="频度")
    threshold_amount = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True, verbose_name="触发阈值(可结算账户余额)"
    )
    payee_bank_name = models.CharField(max_length=128, blank=True, verbose_name="收款银行")
    payee_account_no = models.CharField(max_length=64, blank=True, verbose_name="收款账号")
    payee_account_holder = models.CharField(max_length=128, blank=True, verbose_name="收款账户持有人")
    swift_code = models.CharField(max_length=16, blank=True, verbose_name="SWIFT代码")
    last_run_at = models.DateTimeField(null=True, blank=True, verbose_name="上次执行时间")
    next_run_at = models.DateTimeField(null=True, blank=True, verbose_name="下次执行时间")

    class Meta:
        db_table = "agent_disbursement_schedule"
        verbose_name = "代理自动拨付计划"
        verbose_name_plural = verbose_name
