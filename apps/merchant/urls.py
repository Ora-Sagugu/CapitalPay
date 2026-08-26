"""商户管理 — URL 路由。"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MerchantViewSet

router = DefaultRouter()
router.register(r"merchants", MerchantViewSet, basename="merchant")

urlpatterns_admin = [
    path("", include(router.urls)),
]
