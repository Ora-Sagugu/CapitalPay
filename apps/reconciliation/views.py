"""对账 — API Views (运营管理端)。"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import ReconciliationBatch, ReconciliationDiff, NostroBalanceCheck, ReconAlert, ReconAlertConfig
from .serializers import (
    ReconciliationBatchSerializer, ReconciliationDiffSerializer,
    DiffResolveSerializer, NostroBalanceCheckSerializer,
    ReconAlertSerializer, ReconAlertConfigSerializer,
)
from .engine.diff_handler import DiffHandler
from apps.rbac.permissions import RequiresFeature


class ReconciliationBatchViewSet(RequiresFeature, viewsets.ReadOnlyModelViewSet):
    """对账批次查询 — 运营管理端。"""
    feature_code = "feature:reconciliation"
    queryset = ReconciliationBatch.objects.filter(is_deleted=False)
    serializer_class = ReconciliationBatchSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["bank_code", "status", "reconciliation_date", "recon_type"]
    search_fields = ["batch_no"]
    ordering_fields = ["reconciliation_date", "created_at"]


class ReconciliationDiffViewSet(RequiresFeature, viewsets.ReadOnlyModelViewSet):
    feature_code = "feature:reconciliation"
    """对账差异查询 & 处理 — 运营管理端。"""
    queryset = ReconciliationDiff.objects.filter(is_deleted=False).select_related("batch")
    serializer_class = ReconciliationDiffSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["batch__batch_no", "diff_type", "resolution"]
    search_fields = ["order_no", "bank_txn_id", "prn_code"]

    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve_diff(self, request, pk=None):
        """处理差异。"""
        diff = self.get_object()
        serializer = DiffResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        handler = DiffHandler()
        data = serializer.validated_data
        handler.resolve_diff(
            diff,
            resolution=data["resolution"],
            resolved_by=data["resolved_by"],
            note=data.get("note", ""),
        )
        return Response({"message": "The discrepancy has been resolved"})


class NostroBalanceCheckViewSet(RequiresFeature, viewsets.ReadOnlyModelViewSet):
    feature_code = "feature:reconciliation"
    """Nostro 余额核对查询。"""
    queryset = NostroBalanceCheck.objects.filter(is_deleted=False).select_related("nostro_account")
    serializer_class = NostroBalanceCheckSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["check_date", "is_balanced"]
    ordering_fields = ["check_date", "created_at"]


class ReconAlertViewSet(RequiresFeature, viewsets.ReadOnlyModelViewSet):
    feature_code = "feature:reconciliation"
    """对账差异预警 — 列表与确认。"""
    queryset = ReconAlert.objects.filter(is_deleted=False).select_related("batch")
    serializer_class = ReconAlertSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["status", "severity", "channel"]
    ordering_fields = ["created_at"]

    @action(detail=True, methods=["post"], url_path="ack")
    def ack(self, request, pk=None):
        from django.utils import timezone
        alert = self.get_object()
        alert.status = ReconAlert.AlertStatus.ACKED
        alert.acked_by = request.data.get("acked_by") or getattr(request.user, "username", "") or "admin"
        alert.acked_at = timezone.now()
        alert.save(update_fields=["status", "acked_by", "acked_at", "updated_at"])
        return Response({"message": "Acknowledged", "status": alert.status})


class ReconAlertConfigViewSet(RequiresFeature, viewsets.ViewSet):
    feature_code = "feature:reconciliation"
    """预警配置单例 GET / PATCH。"""

    def list(self, request):
        config = ReconAlertConfig.get_config()
        return Response(ReconAlertConfigSerializer(config).data)

    def create(self, request):
        return self._update(request)

    @action(detail=False, methods=["patch", "put"], url_path="update")
    def update_config(self, request):
        return self._update(request)

    def _update(self, request):
        config = ReconAlertConfig.get_config()
        serializer = ReconAlertConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
