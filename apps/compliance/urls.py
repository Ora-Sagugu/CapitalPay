"""Compliance URL routing"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SanctionListViewSet, SanctionScanRecordViewSet, SanctionHitDetailViewSet

router = DefaultRouter()
router.register(r"sanction-lists", SanctionListViewSet, basename="sanction-list")
router.register(r"sanction-scans", SanctionScanRecordViewSet, basename="sanction-scan")
router.register(r"sanction-hits", SanctionHitDetailViewSet, basename="sanction-hit")

urlpatterns = [
    path("", include(router.urls)),
]
