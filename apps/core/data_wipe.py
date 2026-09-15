"""Wipe business / demo data while preserving SanctionList (OFAC/UN)."""

from __future__ import annotations


def wipe_business_data(*, keep_risk_rating_limits: bool = False, clear_framework_ephemera: bool = False) -> None:
    """Delete transactional and config rows. Never deletes SanctionList.

    QuerySet.delete() is required for MoneyMovement/AuditLog (instance delete is blocked).
    Delete order respects PROTECT foreign keys.
    """
    from apps.account.models import (
        AgentDisbursement,
        AgentDisbursementSchedule,
        DepositRequest,
        DisbursementApproval,
        FundTransfer,
        MoneyMovement,
        NostroAccount,
        UserAccount,
        UserPaymentDetail,
        VaLedgerEntry,
        VirtualAccount,
    )
    from apps.adjustment.models import AdjustmentApplication, AdjustmentApproval
    from apps.agent.models import Agent, AgentCommission, AgentKYC, AgentMerchant
    from apps.compliance.models import SanctionHitDetail, SanctionScanRecord
    from apps.core.models import AuditLog
    from apps.exchange.models import ExchangeRate
    from apps.merchant.models import (
        Merchant,
        MerchantFee,
        MerchantKYC,
        MerchantPaymentProduct,
        MerchantSettlementAccount,
        MerchantSplitConfig,
        MerchantStatusEvent,
    )
    from apps.param.models import (
        BankFeeConfig,
        CoopBank,
        FeeModel,
        RemittanceFeeConfig,
        RiskRatingLimit,
    )
    from apps.payment.models import (
        BankCreditNotification,
        MerchantDailyRemittanceUsage,
        PaymentOrder,
        PRNConfig,
        PrnIssuance,
        RefundFeeConfig,
        RefundOrder,
        RemittanceQuote,
    )
    from apps.rbac.models import (
        OperationLog,
        Permission,
        Role,
        RolePermission,
        SystemUser,
        UserRole,
    )
    from apps.reconciliation.models import (
        NostroBalanceCheck,
        ReconAlert,
        ReconAlertConfig,
        ReconciliationBatch,
        ReconciliationDiff,
    )
    from apps.report.models import ChannelFeeReport, MerchantDailyReport, PlatformOrderSummary
    from apps.routing.models import BankChannel, BankTransaction, RoutingLog, RoutingRule
    from apps.settlement.models import DifferenceWriteOff, FeeShare, SettlementBatch, SettlementDetail
    from apps.user_portal.models import EndUser, RefreshToken, SmsCode, UserOnboarding

    models = [
        AuditLog,
        MoneyMovement,
        RoutingLog,
        ReconAlert,
        VaLedgerEntry,
        DisbursementApproval,
        AgentDisbursement,
        AgentDisbursementSchedule,
        DepositRequest,
        UserPaymentDetail,
        FundTransfer,
        UserAccount,
        VirtualAccount,
        DifferenceWriteOff,
        FeeShare,
        SettlementDetail,
        SettlementBatch,
        NostroBalanceCheck,
        ReconciliationDiff,
        ReconciliationBatch,
        ReconAlertConfig,
        NostroAccount,
        RefundOrder,
        BankCreditNotification,
        PrnIssuance,
        PaymentOrder,
        RemittanceQuote,
        MerchantDailyRemittanceUsage,
        RefundFeeConfig,
        PRNConfig,
        BankTransaction,
        MerchantDailyReport,
        ChannelFeeReport,
        PlatformOrderSummary,
        SanctionHitDetail,
        SanctionScanRecord,
        AdjustmentApproval,
        AdjustmentApplication,
        ExchangeRate,
        AgentCommission,
        AgentMerchant,
        AgentKYC,
        MerchantPaymentProduct,
        MerchantSettlementAccount,
        MerchantFee,
        MerchantKYC,
        MerchantStatusEvent,
        MerchantSplitConfig,
        Merchant,
        Agent,
        BankFeeConfig,
        FeeModel,
        CoopBank,
        RemittanceFeeConfig,
        RoutingRule,
        BankChannel,
        UserRole,
        RolePermission,
        OperationLog,
        SystemUser,
        Role,
        Permission,
        RefreshToken,
        SmsCode,
        UserOnboarding,
        EndUser,
    ]
    if not keep_risk_rating_limits:
        models.append(RiskRatingLimit)

    for model in models:
        model.objects.all().delete()

    if clear_framework_ephemera:
        from django.contrib.admin.models import LogEntry
        from django.contrib.auth.models import User
        from django.contrib.sessions.models import Session

        Session.objects.all().delete()
        LogEntry.objects.all().delete()
        User.objects.all().delete()
