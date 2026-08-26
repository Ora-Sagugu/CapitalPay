from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BankChannelViewSet, RoutingRuleViewSet, RoutingLogViewSet

router = DefaultRouter()
router.register(r"channels", BankChannelViewSet, basename="bank-channel")
router.register(r"rules", RoutingRuleViewSet, basename="routing-rule")
router.register(r"routing-logs", RoutingLogViewSet, basename="routing-log")

urlpatterns = [
    path("", include(router.urls)),
]
