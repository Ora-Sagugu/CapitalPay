"""运营后台 — 终端用户 / Onboarding / 账户 / 支付管理路由。"""
from rest_framework.routers import DefaultRouter
from .views import (
    EndUserAdminViewSet,
    UserOnboardingAdminViewSet,
    EndUserAccountAdminViewSet,
    EndUserPaymentAdminViewSet,
)

router = DefaultRouter()
router.register(r"end-users", EndUserAdminViewSet, basename="end-user-admin")
router.register(r"onboarding", UserOnboardingAdminViewSet, basename="user-onboarding-admin")
router.register(r"end-user-accounts", EndUserAccountAdminViewSet, basename="end-user-account-admin")
router.register(r"end-user-payments", EndUserPaymentAdminViewSet, basename="end-user-payment-admin")

urlpatterns = router.urls
