"""对账 — API Views (运营管理端)。"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import ReconciliationBatch, ReconciliationDiff, NostroBalanceCheck
from .serializers import (
    ReconciliationBatchSerializer, ReconciliationDiffSerializer,
    DiffResolveSerializer, NostroBalanceCheckSerializer,
)
from .engine.diff_handler import DiffHandler


class ReconciliationBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """对账批次查询 — 运营管理端。"""
    queryset = ReconciliationBatch.objects.filter(is_deleted=False)
    serializer_class = ReconciliationBatchSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["bank_code", "status", "reconciliation_date"]
    search_fields = ["batch_no"]
    ordering_fields = ["reconciliation_date", "created_at"]


class ReconciliationDiffViewSet(viewsets.ReadOnlyModelViewSet):
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
        return Response({"message": "差异处理完成"})


class NostroBalanceCheckViewSet(viewsets.ReadOnlyModelViewSet):
    """Nostro 余额核对查询。"""
    queryset = NostroBalanceCheck.objects.filter(is_deleted=False).select_related("nostro_account")
    serializer_class = NostroBalanceCheckSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["check_date", "is_balanced"]
    ordering_fields = ["check_date", "created_at"]
