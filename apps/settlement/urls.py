"""清结算 — URL 路由。"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SettlementBatchViewSet, SettlementDetailViewSet,
    FeeShareViewSet, DifferenceWriteOffViewSet,
)

router = DefaultRouter()
router.register(r"settle-batches", SettlementBatchViewSet, basename="settle-batch")
router.register(r"settle-details", SettlementDetailViewSet, basename="settle-detail")
router.register(r"fee-shares", FeeShareViewSet, basename="fee-share")
router.register(r"difference-writeoffs", DifferenceWriteOffViewSet, basename="diff-writeoff")

urlpatterns = [
    path("", include(router.urls)),
]
