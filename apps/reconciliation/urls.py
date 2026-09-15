"""对账 — URL 路由。"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ReconciliationBatchViewSet, ReconciliationDiffViewSet, NostroBalanceCheckViewSet,
    ReconAlertViewSet, ReconAlertConfigViewSet,
)

router = DefaultRouter()
router.register(r"recon-batches", ReconciliationBatchViewSet, basename="recon-batch")
router.register(r"recon-diffs", ReconciliationDiffViewSet, basename="recon-diff")
router.register(r"nostro-checks", NostroBalanceCheckViewSet, basename="nostro-check")
router.register(r"recon-alerts", ReconAlertViewSet, basename="recon-alert")
router.register(r"recon-alert-config", ReconAlertConfigViewSet, basename="recon-alert-config")

urlpatterns = [
    path("", include(router.urls)),
]
