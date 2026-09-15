"""财务报表 — URL 路由。"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RemittanceReportViewSet,
    MerchantDailyReportViewSet, ChannelFeeReportViewSet,
    PlatformOrderSummaryViewSet, SettlementBatchReportViewSet,
    SettlementDetailReportViewSet, PaymentAnalyticsViewSet,
)

router = DefaultRouter()
router.register(r"reports/analytics", PaymentAnalyticsViewSet, basename="report-analytics")
router.register(r"reports/remittance", RemittanceReportViewSet, basename="report-remittance")
router.register(r"reports/merchant-daily", MerchantDailyReportViewSet, basename="report-merchant-daily")
router.register(r"reports/channel-fee", ChannelFeeReportViewSet, basename="report-channel-fee")
router.register(r"reports/platform-summary", PlatformOrderSummaryViewSet, basename="report-platform-summary")
router.register(r"reports/settle-batches", SettlementBatchReportViewSet, basename="report-settle-batch")
router.register(r"reports/settle-details", SettlementDetailReportViewSet, basename="report-settle-detail")

urlpatterns = [
    path("", include(router.urls)),
]
