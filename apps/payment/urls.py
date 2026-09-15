"""支付交易 — URL 路由。"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaymentOrderViewSet, RefundOrderViewSet, MerchantOrderViewSet, MerchantRefundViewSet
from .views_bank_notifications import BankCreditNotificationViewSet

# 运营管理端
admin_router = DefaultRouter()
admin_router.register(r"orders", PaymentOrderViewSet, basename="admin-order")
admin_router.register(r"refunds", RefundOrderViewSet, basename="admin-refund")
admin_router.register(r"bank-notifications", BankCreditNotificationViewSet, basename="admin-bank-notification")

# 商户服务端
merchant_router = DefaultRouter()
merchant_router.register(r"merchant/orders", MerchantOrderViewSet, basename="merchant-order")
merchant_router.register(r"merchant/refunds", MerchantRefundViewSet, basename="merchant-refund")

urlpatterns_admin = [
    path("", include(admin_router.urls)),
]

urlpatterns_merchant = [
    path("", include(merchant_router.urls)),
]
