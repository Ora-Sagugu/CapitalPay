"""Agent API views"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from django.db.models import Count, Q

from .models import Agent, AgentMerchant, AgentCommission, AgentKYC
from .serializers import (
    AgentSerializer, AgentListSerializer,
    AgentMerchantSerializer, AgentCommissionSerializer,
    AgentKYCSerializer,
)
from .services import ensure_agent_accounts, ensure_agent_api_credentials, build_agent_fee_overview
from apps.rbac.authentication import JWTAuthentication
from apps.rbac.permissions import RequiresFeature


class AgentViewSet(RequiresFeature, viewsets.ModelViewSet):
    """代理商管理 — 企业资料和结算银行信息"""
    authentication_classes = [JWTAuthentication]
    feature_code = "feature:agents"
    ACTION_FEATURES = {
        "fee_overview": "feature:agent_fees",
        "suspend": "feature:agents.approve",
        "activate": "feature:agents.approve",
    }
    queryset = Agent.objects.filter(is_deleted=False).select_related("kyc")
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status"]
    search_fields = [
        "agent_no", "agent_name", "contact_name", "contact_phone",
        "legal_person", "business_license_no", "settlement_account_no",
    ]
    ordering_fields = ["created_at", "agent_name", "commission_rate"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            Agent.objects.filter(is_deleted=False)
            .select_related("kyc")
            .annotate(
                customer_count=Count(
                    "direct_merchants",
                    filter=Q(direct_merchants__is_deleted=False),
                    distinct=True,
                ),
                order_count=Count(
                    "direct_merchants__orders",
                    filter=Q(
                        direct_merchants__is_deleted=False,
                        direct_merchants__orders__is_deleted=False,
                    ),
                    distinct=True,
                ),
            )
        )

    def get_serializer_class(self):
        if self.action == "list":
            return AgentListSerializer
        return AgentSerializer

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        qs = Agent.objects.filter(is_deleted=False)
        return Response({
            "total": qs.count(),
            "active": qs.filter(status="ACTIVE").count(),
            "suspended": qs.filter(status="SUSPENDED").count(),
            "closed": qs.filter(status="CLOSED").count(),
        })

    # ── 状态管理 ──

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        agent = self.get_object()
        agent.status = "SUSPENDED"
        agent.save(update_fields=["status", "updated_at"])
        return Response({"message": "The agent has been suspended"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        agent = self.get_object()
        agent.status = "ACTIVE"
        agent.save(update_fields=["status", "updated_at"])
        return Response({"message": "The agent has been activated"}, status=status.HTTP_200_OK)

    # ── 关联查询 ──

    @action(detail=True, methods=["get"])
    def merchants(self, request, pk=None):
        agent = self.get_object()
        relations = agent.merchant_relations.filter(is_deleted=False)
        serializer = AgentMerchantSerializer(relations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def commissions(self, request, pk=None):
        agent = self.get_object()
        qs = agent.commissions.all()
        serializer = AgentCommissionSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="fee-overview")
    def fee_overview(self, request, pk=None):
        agent = self.get_object()
        return Response(build_agent_fee_overview(agent))


class AgentMerchantViewSet(RequiresFeature, viewsets.ModelViewSet):
    """代理商户关联管理"""
    authentication_classes = [JWTAuthentication]
    feature_code = "feature:agents"
    queryset = AgentMerchant.objects.filter(is_deleted=False)
    serializer_class = AgentMerchantSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["agent__agent_no", "merchant__merchant_no"]

    def perform_create(self, serializer):
        if AgentMerchant.objects.filter(
            agent=serializer.validated_data["agent"],
            merchant=serializer.validated_data["merchant"],
            is_deleted=False,
        ).exists():
            from apps.core.exceptions import BusinessException
            raise BusinessException(code="DUPLICATE_RELATION", message="This agent–customer relationship already exists")
        serializer.save()


class AgentCommissionViewSet(RequiresFeature, viewsets.ReadOnlyModelViewSet):
    """代理佣金查询"""
    authentication_classes = [JWTAuthentication]
    feature_code = "feature:agent_fees"
    queryset = AgentCommission.objects.all()
    serializer_class = AgentCommissionSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["agent__agent_no", "merchant__merchant_no", "status"]
    ordering_fields = ["created_at", "commission_amount"]
    ordering = ["-created_at"]


class AgentKYCViewSet(RequiresFeature, viewsets.ModelViewSet):
    """代理尽职调查 / KYC"""
    authentication_classes = [JWTAuthentication]
    feature_code = "feature:agents"
    ACTION_FEATURES = {
        "submit_kyc": "feature:agents.approve",
        "review_kyc": "feature:agents.approve",
    }
    queryset = AgentKYC.objects.filter(is_deleted=False).select_related("agent")
    serializer_class = AgentKYCSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["kyc_status", "tier", "agent__agent_no"]
    search_fields = ["agent__agent_no", "agent__agent_name", "legal_person"]
    ordering = ["-created_at"]

    @action(detail=True, methods=["post"], url_path="submit")
    def submit_kyc(self, request, pk=None):
        kyc = self.get_object()
        kyc.submit(operator=getattr(request.user, "username", ""))
        return Response({"message": "Due-diligence materials have been submitted", "kyc_status": kyc.kyc_status})

    @action(detail=True, methods=["post"], url_path="review")
    def review_kyc(self, request, pk=None):
        kyc = self.get_object()
        action_type = request.data.get("action")
        comment = (request.data.get("reason") or request.data.get("comment") or "").strip()
        reviewer = request.data.get("reviewed_by") or getattr(request.user, "username", "")
        if action_type == "approve":
            kyc.kyc_status = AgentKYC.KycStatus.UNDER_REVIEW
            kyc.approve(reviewer=reviewer, comment=comment or "Approved")
            agent = kyc.agent
            if agent.status != "ACTIVE":
                agent.status = "ACTIVE"
                agent.save(update_fields=["status", "updated_at"])
            ensure_agent_api_credentials(agent)
            ensure_agent_accounts(agent)
            accounts = [
                {
                    "account_no": a.account_no,
                    "account_type": a.account_type,
                    "currency": a.currency,
                    "balance": str(a.balance),
                }
                for a in agent.nostro_accounts.filter(is_deleted=False)
            ]
            return Response({
                "message": "Due diligence has been approved",
                "kyc_status": kyc.kyc_status,
                "accounts": accounts,
            })
        if action_type == "reject":
            if not comment:
                return Response({"detail": "Grounds for rejection are required"}, status=status.HTTP_400_BAD_REQUEST)
            kyc.reject(reviewer=reviewer, comment=comment)
            return Response({"message": "Due diligence has been rejected", "kyc_status": kyc.kyc_status})
        return Response({"detail": "action must be approve or reject"}, status=status.HTTP_400_BAD_REQUEST)
