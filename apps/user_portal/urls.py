"""用户端路由 — 注册、登录、个人中心、账户绑定、支付历史、首次登录资料。"""
from rest_framework.routers import DefaultRouter
from .views import (
    UserAuthViewSet, UserProfileViewSet,
    UserAccountViewSet, UserPaymentViewSet,
    UserOnboardingViewSet, UserOnboardingAdminViewSet,
)

router = DefaultRouter()
router.register(r"auth", UserAuthViewSet, basename="user-auth")
router.register(r"profile", UserProfileViewSet, basename="user-profile")
router.register(r"accounts", UserAccountViewSet, basename="user-account")
router.register(r"payments", UserPaymentViewSet, basename="user-payment")
router.register(r"onboarding", UserOnboardingViewSet, basename="user-onboarding")
router.register(r"admin/onboarding", UserOnboardingAdminViewSet, basename="user-onboarding-admin")

urlpatterns = router.urls
