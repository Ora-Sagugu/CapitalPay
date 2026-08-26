"""Agent API views"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Agent, AgentMerchant, AgentCommission, AgentFeeConfig, AgentKYC
from .serializers import (
    AgentSerializer, AgentListSerializer,
    AgentMerchantSerializer, AgentCommissionSerializer,
    AgentFeeConfigSerializer, AgentKYCSerializer,
)
from .services import generate_agent_no, generate_commission_no
from apps.rbac.authentication import JWTAuthentication
from apps.rbac.permissions import require_permission


class AgentViewSet(viewsets.ModelViewSet):
    """代理商管理 — 企业资料和结算银行信息"""
    authentication_classes = [JWTAuthentication]
    queryset = Agent.objects.filter(is_deleted=False).select_related("kyc")
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "level"]
    search_fields = [
        "agent_no", "agent_name", "contact_name", "contact_phone",
        "legal_person", "business_license_no", "settlement_account_no",
    ]
    ordering_fields = ["created_at", "agent_name", "commission_rate"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return AgentListSerializer
        return AgentSerializer

    def perform_create(self, serializer):
        serializer.save(agent_no=generate_agent_no())

    # ── 状态管理 ──

    @action(detail=True, methods=["post"])
    @require_permission("merchant:approve")
    def suspend(self, request, pk=None):
        agent = self.get_object()
        agent.status = "SUSPENDED"
        agent.save(update_fields=["status", "updated_at"])
        return Response({"message": "代理商已暂停"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    @require_permission("merchant:approve")
    def activate(self, request, pk=None):
        agent = self.get_object()
        agent.status = "ACTIVE"
        agent.save(update_fields=["status", "updated_at"])
        return Response({"message": "代理商已激活"}, status=status.HTTP_200_OK)

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


class AgentMerchantViewSet(viewsets.ModelViewSet):
    """代理商户关联管理"""
    authentication_classes = [JWTAuthentication]
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
            raise BusinessException(code="DUPLICATE_RELATION", message="该代理-商户关联已存在")
        serializer.save()


class AgentCommissionViewSet(viewsets.ReadOnlyModelViewSet):
    """代理佣金查询"""
    authentication_classes = [JWTAuthentication]
    queryset = AgentCommission.objects.all()
    serializer_class = AgentCommissionSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["agent__agent_no", "merchant__merchant_no", "status"]
    ordering_fields = ["created_at", "commission_amount"]
    ordering = ["-created_at"]


class AgentFeeConfigViewSet(viewsets.ModelViewSet):
    """代理商费率配置管理 — 差异化手续费与分润比例"""
    authentication_classes = [JWTAuthentication]
    queryset = AgentFeeConfig.objects.filter(is_deleted=False).select_related("agent")
    serializer_class = AgentFeeConfigSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["agent__agent_no", "fee_type", "currency", "is_active"]
    search_fields = ["agent__agent_name"]
    ordering_fields = ["agent__agent_name", "fee_type", "currency", "rate"]
    ordering = ["agent__agent_name", "fee_type", "currency"]

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """费率统计：按代理汇总"""
        agent_id = request.query_params.get("agent_id")
        qs = AgentFeeConfig.objects.filter(is_deleted=False)
        if agent_id:
            qs = qs.filter(agent_id=agent_id)

        total_configs = qs.count()
        active_configs = qs.filter(is_active=True).count()
        currencies = list(qs.filter(is_active=True).values_list("currency", flat=True).distinct())
        fee_types = list(qs.filter(is_active=True).values_list("fee_type", flat=True).distinct())

        return Response({
            "total_configs": total_configs,
            "active_configs": active_configs,
            "covered_currencies": currencies,
            "covered_fee_types": fee_types,
            "currency_count": len(currencies),
            "fee_type_count": len(fee_types),
        })

    @action(detail=True, methods=["post"], url_path="toggle")
    def toggle(self, request, pk=None):
        """启停费率配置"""
        config = self.get_object()
        config.is_active = not config.is_active
        config.save(update_fields=["is_active", "updated_at"])
        return Response({
            "message": "费率配置已" + ("启用" if config.is_active else "停用"),
            "is_active": config.is_active,
        })


class AgentKYCViewSet(viewsets.ModelViewSet):
    """代理尽职调查 / KYC"""
    authentication_classes = [JWTAuthentication]
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
        return Response({"message": "尽调资料已提交", "kyc_status": kyc.kyc_status})

    @action(detail=True, methods=["post"], url_path="review")
    @require_permission("merchant:approve")
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
            return Response({"message": "尽调已通过", "kyc_status": kyc.kyc_status})
        if action_type == "reject":
            if not comment:
                return Response({"detail": "驳回须填写原因"}, status=status.HTTP_400_BAD_REQUEST)
            kyc.reject(reviewer=reviewer, comment=comment)
            return Response({"message": "尽调已驳回", "kyc_status": kyc.kyc_status})
        return Response({"detail": "action must be approve or reject"}, status=status.HTTP_400_BAD_REQUEST)
