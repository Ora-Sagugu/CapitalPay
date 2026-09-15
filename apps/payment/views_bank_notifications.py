"""运营管理端 — 银行入金通知收件箱。"""
from django.db import models as db_models
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.rbac.permissions import RequiresFeature
from .models import BankCreditNotification
from .serializers import (
    BankCreditNotificationDetailSerializer,
    BankCreditNotificationSerializer,
    SimulateBankCreditSerializer,
)
from .services.bank_notification import simulate_credit


class BankCreditNotificationViewSet(RequiresFeature, viewsets.ReadOnlyModelViewSet):
    """Inbound bank credits matched by PRN (mock ingest; no bank API)."""

    feature_code = "feature:bank_notifications"
    queryset = BankCreditNotification.objects.filter(is_deleted=False).select_related("order", "merchant")
    serializer_class = BankCreditNotificationSerializer
    lookup_field = "notification_no"
    lookup_url_kwarg = "notification_no"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return BankCreditNotificationDetailSerializer
        return BankCreditNotificationSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = (self.request.query_params.get("status") or "").strip().upper()
        if status_param:
            qs = qs.filter(status=status_param)
        currency = (self.request.query_params.get("currency") or "").strip().upper()
        if currency:
            qs = qs.filter(currency=currency)
        bank = (self.request.query_params.get("bank") or self.request.query_params.get("bank_code") or "").strip()
        if bank:
            qs = qs.filter(
                db_models.Q(bank_code__icontains=bank) | db_models.Q(bank_name__icontains=bank)
            )
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                db_models.Q(notification_no__icontains=search)
                | db_models.Q(txn_id__icontains=search)
                | db_models.Q(prn_code__icontains=search)
                | db_models.Q(order_no__icontains=search)
                | db_models.Q(merchant_no__icontains=search)
                | db_models.Q(merchant_name__icontains=search)
                | db_models.Q(bank_name__icontains=search)
                | db_models.Q(remark__icontains=search)
            )
        return qs.order_by("-txn_time", "-created_at")

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        qs = BankCreditNotification.objects.filter(is_deleted=False)
        status_counts = {
            row["status"]: row["cnt"]
            for row in qs.values("status").annotate(cnt=db_models.Count("id"))
        }
        today = timezone.localdate()
        today_qs = qs.filter(txn_time__date=today)
        return Response({
            "total_count": qs.count(),
            "matched": status_counts.get(BankCreditNotification.Status.MATCHED, 0),
            "mismatch": status_counts.get(BankCreditNotification.Status.MISMATCH, 0),
            "unmatched": status_counts.get(BankCreditNotification.Status.UNMATCHED, 0),
            "received": status_counts.get(BankCreditNotification.Status.RECEIVED, 0),
            "today_count": today_qs.count(),
            "today_matched": today_qs.filter(status=BankCreditNotification.Status.MATCHED).count(),
        })

    @action(detail=False, methods=["post"], url_path="simulate")
    def simulate(self, request):
        serializer = SimulateBankCreditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notification = simulate_credit(serializer.validated_data)
        return Response(BankCreditNotificationDetailSerializer(notification).data, status=201)
