from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AgentViewSet, AgentMerchantViewSet, AgentCommissionViewSet,
    AgentFeeConfigViewSet, AgentKYCViewSet,
)

router = DefaultRouter()
router.register(r"agents", AgentViewSet, basename="agent")
router.register(r"agent-merchants", AgentMerchantViewSet, basename="agent-merchant")
router.register(r"agent-commissions", AgentCommissionViewSet, basename="agent-commission")
router.register(r"agent-fee-configs", AgentFeeConfigViewSet, basename="agent-fee-config")
router.register(r"agent-kyc", AgentKYCViewSet, basename="agent-kyc")

urlpatterns = [
    path("", include(router.urls)),
]
