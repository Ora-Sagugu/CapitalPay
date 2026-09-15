"""账户体系 — API Views。"""
from decimal import Decimal
from django.db import models as db_models
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import (
    NostroAccount, FundTransfer, UserPaymentDetail, DepositRequest,
    VirtualAccount, AgentDisbursement, DisbursementApproval,
)
from .serializers import (
    NostroAccountSerializer, FundTransferSerializer, UserPaymentDetailSerializer,
    DepositRequestSerializer, VirtualAccountSerializer, AgentDisbursementSerializer,
)
from .services import (
    AccountService, DisbursementService,
    group_virtual_accounts_by_customer, parse_page_params,
    serialize_virtual_account_transactions,
)
from apps.rbac.permissions import RequiresFeature


def build_account_transactions(account):
    """构建账户交易流水（入账 Deposit + 资金调拨 FundTransfer），按时间倒序。

    虚拟账户(VA)为逻辑账户，其交易流水即母账户流水。
    """
    transactions = []

    deposits = account.deposits.filter(is_deleted=False).order_by("-created_at")
    for d in deposits:
        transactions.append({
            "id": f"dep_{d.id}",
            "type": "Deposit",
            "type_class": "deposit",
            "direction": "in",
            "amount": str(d.amount),
            "currency": d.currency,
            "status": d.status,
            "status_label": DEPOSIT_STATUS_MAP.get(d.status, d.status),
            "ref_no": d.deposit_no,
            "remark": d.remark or "",
            "created_at": str(d.created_at),
        })

    out_transfers = account.out_transfers.filter(is_deleted=False).order_by("-created_at")
    for t in out_transfers:
        transactions.append({
            "id": f"out_{t.id}",
            "type": "Transfer Out",
            "type_class": "transfer-out",
            "direction": "out",
            "amount": f"-{t.amount}",
            "currency": t.currency,
            "status": t.status,
            "status_label": TRANSFER_STATUS_MAP.get(t.status, t.status),
            "ref_no": t.transfer_no,
            "remark": f"Transferred to {t.to_account.bank_name} — {t.remark}" if t.remark else f"Transferred to {t.to_account.bank_name}",
            "created_at": str(t.created_at),
        })

    in_transfers = account.in_transfers.filter(is_deleted=False).order_by("-created_at")
    for t in in_transfers:
        transactions.append({
            "id": f"in_{t.id}",
            "type": "Transfer In",
            "type_class": "transfer-in",
            "direction": "in",
            "amount": str(t.amount),
            "currency": t.currency,
            "status": t.status,
            "status_label": TRANSFER_STATUS_MAP.get(t.status, t.status),
            "ref_no": t.transfer_no,
            "remark": f"Transferred from {t.from_account.bank_name} — {t.remark}" if t.remark else f"Transferred from {t.from_account.bank_name}",
            "created_at": str(t.created_at),
        })

    transactions.sort(key=lambda x: x["created_at"], reverse=True)
    return transactions


DEPOSIT_STATUS_MAP = {
    "PENDING": "Pending Review",
    "APPROVED": "Approved",
    "REJECTED": "Rejected",
}
TRANSFER_STATUS_MAP = {
    "PENDING": "Pending",
    "PROCESSING": "Processing",
    "SUCCESS": "Succeeded",
    "FAILED": "Failed",
}


class NostroAccountViewSet(RequiresFeature, viewsets.ModelViewSet):
    """Nostro 账户管理 — 支持增删改查、充值、注销、交易流水。"""
    feature_code = "feature:accounts"
    queryset = NostroAccount.objects.filter(is_deleted=False).select_related("merchant", "agent")
    serializer_class = NostroAccountSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        merchant_id = self.request.query_params.get("merchant_id")
        if merchant_id:
            qs = qs.filter(merchant_id=merchant_id)
        agent_id = self.request.query_params.get("agent_id")
        if agent_id:
            qs = qs.filter(agent_id=agent_id)
        currency = self.request.query_params.get("currency")
        if currency:
            qs = qs.filter(currency=currency)
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")
        return qs

    def perform_destroy(self, instance):
        """软删除 — 设置 is_deleted=True，不真正删除数据库记录。"""
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted", "updated_at"])

    @action(detail=True, methods=["post"], url_path="recharge")
    def recharge(self, request, pk=None):
        """账户充值 — 增加账户余额。"""
        account = self.get_object()
        amount_str = request.data.get("amount")
        try:
            amount = Decimal(str(amount_str))
        except (ValueError, TypeError):
            return Response({"detail": "A valid credit amount is required"}, status=status.HTTP_400_BAD_REQUEST)
        if amount <= 0:
            return Response({"detail": "The credit amount must be greater than zero"}, status=status.HTTP_400_BAD_REQUEST)

        account.balance = account.balance + amount
        account.save(update_fields=["balance", "updated_at"])
        return Response({
            "message": f"The credit has been posted: {account.currency} +{amount:,.2f}",
            "balance": str(account.balance),
            "currency": account.currency,
        })

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        """注销账户 — 设置 is_active=False，记录注销原因和时间。"""
        account = self.get_object()
        reason = request.data.get("reason", "").strip()
        if not reason:
            return Response({"detail": "Grounds for closure are required"}, status=status.HTTP_400_BAD_REQUEST)

        account.is_active = False
        account.closed_at = timezone.now()
        account.close_reason = reason
        account.save(update_fields=["is_active", "closed_at", "close_reason", "updated_at"])
        return Response({
            "message": f"Account {account.account_no} has been closed",
            "closed_at": str(account.closed_at),
        })

    @action(detail=True, methods=["get"], url_path="transactions")
    def transactions(self, request, pk=None):
        """获取账户交易流水 — 包含入账(Deposit)和资金调拨(FundTransfer)。"""
        account = self.get_object()
        transactions = build_account_transactions(account)
        return Response({
            "account_no": account.account_no,
            "bank_name": account.bank_name,
            "bank_code": account.bank_code,
            "currency": account.currency,
            "balance": str(account.balance),
            "transactions": transactions,
            "count": len(transactions),
        })

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        qs = NostroAccount.objects.filter(is_deleted=False)
        currencies = list(qs.values_list("currency", flat=True).distinct())
        by_ccy = {}
        for row in qs.values("currency").annotate(total=db_models.Sum("balance")):
            by_ccy[row["currency"]] = float(row["total"] or 0)
        return Response({
            "total": qs.count(),
            "active": qs.filter(is_active=True).count(),
            "currency_count": len(currencies),
            "currencies": currencies,
            "balances": by_ccy,
            "cny_total": by_ccy.get("CNY", 0),
            "usd_total": by_ccy.get("USD", 0),
            "hkd_total": by_ccy.get("HKD", 0),
            "eur_total": by_ccy.get("EUR", 0),
        })


class FundTransferViewSet(RequiresFeature, viewsets.ModelViewSet):
    """资金调拨管理。"""
    feature_code = "feature:fund_transfers"
    queryset = FundTransfer.objects.filter(is_deleted=False)
    serializer_class = FundTransferSerializer
    lookup_field = "transfer_no"
    lookup_url_kwarg = "transfer_no"
    service = AccountService()

    @action(detail=True, methods=["post"], url_path="execute")
    def execute(self, request, transfer_no=None):
        """执行资金调拨。"""
        transfer = self.get_object()
        self.service.execute_transfer(transfer)
        return Response({"message": "The internal fund transfer has been executed"})


class UserPaymentDetailViewSet(RequiresFeature, viewsets.ReadOnlyModelViewSet):
    """用户支付明细查询。"""
    feature_code = "feature:users"
    serializer_class = UserPaymentDetailSerializer

    def get_queryset(self):
        user_id = self.request.query_params.get("user_id")
        if not user_id:
            return UserPaymentDetail.objects.none()
        return UserPaymentDetail.objects.filter(
            user_id=user_id, is_deleted=False
        ).select_related("order").order_by("-pay_time")


class DepositRequestViewSet(RequiresFeature, viewsets.ModelViewSet):
    """存款/入账管理 — 客户提交存款请求，运营审核。审核通过后资金自动划入账户。"""
    feature_code = "feature:deposits"
    ACTION_FEATURES = {
        "review": "feature:deposits.approve",
    }
    queryset = DepositRequest.objects.filter(is_deleted=False).select_related("merchant", "agent", "account")
    serializer_class = DepositRequestSerializer
    lookup_field = "deposit_no"
    lookup_url_kwarg = "deposit_no"

    def get_queryset(self):
        qs = super().get_queryset()
        currency = self.request.query_params.get("currency")
        if currency:
            qs = qs.filter(currency=currency)
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())
        merchant_id = self.request.query_params.get("merchant")
        if merchant_id:
            qs = qs.filter(merchant_id=merchant_id)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                db_models.Q(deposit_no__icontains=search) |
                db_models.Q(merchant__merchant_name__icontains=search) |
                db_models.Q(agent__agent_name__icontains=search) |
                db_models.Q(remark__icontains=search)
            )
        return qs.order_by("-created_at")

    @action(detail=True, methods=["post"], url_path="review")
    def review(self, request, deposit_no=None):
        """审核存款 — approve/reject。通过后贷记客户 VA / 代理币种池。"""
        from apps.account.services import AccountService

        deposit = self.get_object()
        action_type = request.data.get("action")
        if action_type not in ("approve", "reject"):
            return Response(
                {"detail": "action must be approve or reject"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reviewer = request.data.get("reviewed_by", "") or getattr(request.user, "username", "")
        service = AccountService()
        if action_type == "reject":
            deposit = service.reject_deposit(
                deposit,
                reviewer=reviewer,
                reason=request.data.get("reason", ""),
            )
        else:
            deposit = service.approve_deposit(
                deposit,
                reviewer=reviewer,
                comment=request.data.get("reason", "") or request.data.get("comment", ""),
            )

        return Response({
            "message": f"The deposit has been {'approved' if action_type == 'approve' else 'rejected'}",
            "status": deposit.status,
            "amount": str(deposit.amount),
            "currency": deposit.currency,
        })

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """充值统计 — 按币种和状态聚合数据。"""
        from django.db.models import Sum, Count
        qs = DepositRequest.objects.filter(is_deleted=False)

        # 状态统计
        status_counts = dict(
            DepositRequest.objects.filter(is_deleted=False).values_list("status").annotate(cnt=Count("id"))
        )

        # 币种统计
        currency_stats = list(
            DepositRequest.objects.filter(is_deleted=False).values("currency").annotate(
                total=Sum("amount"), count=Count("id")
            ).order_by("-total")
        )

        # 今日统计
        today = timezone.now().date()
        today_approved = DepositRequest.objects.filter(
            is_deleted=False, status="APPROVED", reviewed_at__date=today
        ).aggregate(total=Sum("amount"))

        return Response({
            "total_count": qs.count(),
            "pending": status_counts.get("PENDING", 0),
            "approved": status_counts.get("APPROVED", 0),
            "rejected": status_counts.get("REJECTED", 0),
            "currency_stats": [
                {
                    "currency": cs["currency"],
                    "total_amount": str(cs["total"] or 0),
                    "count": cs["count"],
                }
                for cs in currency_stats
            ],
            "today_approved": str(today_approved["total"] or 0),
        })


class VirtualAccountViewSet(RequiresFeature, viewsets.ModelViewSet):
    """虚拟账户 (Virtual Account) 管理 — 伞形母账户下的逻辑分账子账号。

    支持增删改查、停用/启用/注销、交易流水、统计。
    """
    feature_code = "feature:virtual_accounts"
    queryset = (
        VirtualAccount.objects.filter(is_deleted=False)
        .select_related("master_account", "merchant", "agent", "order")
    )
    serializer_class = VirtualAccountSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        merchant_id = self.request.query_params.get("merchant_id")
        if merchant_id:
            qs = qs.filter(merchant_id=merchant_id)
        agent_id = self.request.query_params.get("agent_id")
        if agent_id:
            qs = qs.filter(agent_id=agent_id)
        va_type = self.request.query_params.get("va_type")
        if va_type:
            qs = qs.filter(va_type=va_type)
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        currency = self.request.query_params.get("currency")
        if currency:
            qs = qs.filter(currency=currency)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                db_models.Q(va_number__icontains=search)
                | db_models.Q(reference__icontains=search)
                | db_models.Q(label__icontains=search)
                | db_models.Q(merchant__merchant_name__icontains=search)
                | db_models.Q(merchant__merchant_no__icontains=search)
            )
        return qs

    def perform_create(self, serializer):
        super().perform_create(serializer)

    def perform_update(self, serializer):
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        """软删除 — 设置 is_deleted=True。"""
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted", "updated_at"])

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        """停用虚拟账户 — 记录原因与时间。"""
        va = self.get_object()
        if va.status == VirtualAccount.VaStatus.REVOKED:
            return Response(
                {"code": "VA_ALREADY_REVOKED", "detail": "Virtual account already revoked"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reason = request.data.get("reason", "").strip()
        if not reason:
            return Response(
                {"code": "PARAM_MISSING", "detail": "Reason is required to deactivate"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        va.status = VirtualAccount.VaStatus.INACTIVE
        va.closed_at = timezone.now()
        va.close_reason = reason
        va.save(update_fields=["status", "closed_at", "close_reason", "updated_at"])
        return Response({
            "code": "VA_DEACTIVATED",
            "message": f"Virtual account {va.va_number} deactivated",
            "status": va.status,
        })

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        """重新启用虚拟账户。"""
        va = self.get_object()
        va.status = VirtualAccount.VaStatus.ACTIVE
        va.closed_at = None
        va.close_reason = ""
        va.save(update_fields=["status", "closed_at", "close_reason", "updated_at"])
        return Response({
            "code": "VA_ACTIVATED",
            "message": f"Virtual account {va.va_number} activated",
            "status": va.status,
        })

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        """注销虚拟账户 — 不可逆。"""
        va = self.get_object()
        reason = request.data.get("reason", "").strip() or "Revoked by operator"
        va.status = VirtualAccount.VaStatus.REVOKED
        va.closed_at = timezone.now()
        va.close_reason = reason
        va.save(update_fields=["status", "closed_at", "close_reason", "updated_at"])
        return Response({
            "code": "VA_REVOKED",
            "message": f"Virtual account {va.va_number} revoked",
            "status": va.status,
        })

    @action(detail=False, methods=["get"], url_path="by-customer")
    def by_customer(self, request):
        """按客户汇总虚拟账户 — 一行一个 Customer，详情含该客户全部 VA。"""
        matched = self.get_queryset().filter(merchant_id__isnull=False)
        page, page_size = parse_page_params(
            request.query_params.get("page"), request.query_params.get("page_size"),
        )
        return Response(group_virtual_accounts_by_customer(matched, page=page, page_size=page_size))

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """虚拟账户统计 — 按状态/类型聚合。"""
        from django.db.models import Count
        qs = VirtualAccount.objects.filter(is_deleted=False)
        status_counts = dict(qs.values_list("status").annotate(cnt=Count("id")))
        type_counts = dict(qs.values_list("va_type").annotate(cnt=Count("id")))
        return Response({
            "total": qs.count(),
            "active": status_counts.get("ACTIVE", 0),
            "inactive": status_counts.get("INACTIVE", 0),
            "revoked": status_counts.get("REVOKED", 0),
            "vla": type_counts.get("VLA", 0),
            "vav": type_counts.get("VAV", 0),
        })

    @action(detail=True, methods=["get"], url_path="transactions")
    def transactions(self, request, pk=None):
        """虚拟账户交易流水 — 优先返回分类账分录。"""
        return Response(serialize_virtual_account_transactions(self.get_object()))


class AgentDisbursementViewSet(RequiresFeature, viewsets.ModelViewSet):
    """代理资金拨付 — 双授权 + 二审后自动出金。"""
    feature_code = "feature:disbursements"
    ACTION_FEATURES = {
        "approve": "feature:disbursements.approve",
        "reject": "feature:disbursements.approve",
        "execute": "feature:disbursements.approve",
    }
    queryset = AgentDisbursement.objects.filter(is_deleted=False).select_related("agent").prefetch_related("approvals")
    serializer_class = AgentDisbursementSerializer
    lookup_field = "disbursement_no"
    lookup_url_kwarg = "disbursement_no"
    service = DisbursementService()

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        agent_id = self.request.query_params.get("agent") or self.request.query_params.get("agent_id")
        if agent_id:
            qs = qs.filter(agent_id=agent_id)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                db_models.Q(disbursement_no__icontains=search)
                | db_models.Q(agent__agent_name__icontains=search)
                | db_models.Q(payee_account_no__icontains=search)
            )
        return qs

    def _operator(self, request):
        return (
            request.data.get("approver")
            or request.data.get("operator")
            or getattr(request.user, "username", "")
            or "system"
        )

    def _step_for(self, disbursement):
        if disbursement.status == AgentDisbursement.DisbursementStatus.PENDING_FIRST_APPROVAL:
            return DisbursementApproval.ApprovalStep.FIRST
        if disbursement.status == AgentDisbursement.DisbursementStatus.PENDING_SECOND_APPROVAL:
            return DisbursementApproval.ApprovalStep.SECOND
        return None

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, disbursement_no=None):
        from apps.core.exceptions import BusinessException
        disbursement = self.get_object()
        step = request.data.get("step") or self._step_for(disbursement)
        if not step:
            return Response({"detail": "The current status does not permit authorisation"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            disbursement = self.service.approve(
                disbursement, step, self._operator(request), request.data.get("comment") or "",
            )
        except BusinessException as e:
            return Response({"code": e.code, "message": e.message}, status=e.http_status)
        auto_executed = False
        if disbursement.status == AgentDisbursement.DisbursementStatus.APPROVED:
            try:
                disbursement = self.service.execute(disbursement)
                auto_executed = True
            except BusinessException as e:
                disbursement.refresh_from_db()
                return Response({
                    "message": "Second authorisation succeeded, but automated payout failed",
                    "status": disbursement.status,
                    "code": e.code,
                    "fail_reason": disbursement.fail_reason or e.message,
                    "auto_executed": False,
                }, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            "message": "Authorisation recorded",
            "status": disbursement.status,
            "auto_executed": auto_executed,
        })

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, disbursement_no=None):
        from apps.core.exceptions import BusinessException
        disbursement = self.get_object()
        step = request.data.get("step") or self._step_for(disbursement)
        if not step:
            return Response({"detail": "The current status does not permit rejection"}, status=status.HTTP_400_BAD_REQUEST)
        comment = (request.data.get("comment") or request.data.get("reason") or "").strip()
        try:
            disbursement = self.service.reject(disbursement, step, self._operator(request), comment)
        except BusinessException as e:
            return Response({"code": e.code, "message": e.message}, status=e.http_status)
        return Response({"message": "The disbursement has been rejected", "status": disbursement.status})

    @action(detail=True, methods=["post"], url_path="execute")
    def execute(self, request, disbursement_no=None):
        from apps.core.exceptions import BusinessException
        disbursement = self.get_object()
        try:
            disbursement = self.service.execute(disbursement)
        except BusinessException as e:
            return Response({"code": e.code, "message": e.message, "fail_reason": getattr(disbursement, "fail_reason", "")}, status=e.http_status)
        return Response({"message": "The disbursement has been executed", "status": disbursement.status})
