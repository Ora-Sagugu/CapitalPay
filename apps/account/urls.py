"""账户体系 — URL 路由。"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NostroAccountViewSet, FundTransferViewSet, UserPaymentDetailViewSet, DepositRequestViewSet, VirtualAccountViewSet

router = DefaultRouter()
router.register(r"nostro-accounts", NostroAccountViewSet, basename="nostro-account")
router.register(r"fund-transfers", FundTransferViewSet, basename="fund-transfer")
router.register(r"user-payment-details", UserPaymentDetailViewSet, basename="user-payment-detail")
router.register(r"deposits", DepositRequestViewSet, basename="deposit")
router.register(r"virtual-accounts", VirtualAccountViewSet, basename="virtual-account")

urlpatterns = [
    path("", include(router.urls)),
]
