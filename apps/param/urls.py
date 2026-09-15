from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CoopBankViewSet, FeeModelViewSet, BankFeeConfigViewSet,
    RiskRatingLimitViewSet, RemittanceFeeConfigView,
)

router = DefaultRouter()
router.register(r"coop-banks", CoopBankViewSet, basename="coop-bank")
router.register(r"fee-models", FeeModelViewSet, basename="fee-model")
router.register(r"bank-fee-configs", BankFeeConfigViewSet, basename="bank-fee-config")
router.register(r"risk-rating-limits", RiskRatingLimitViewSet, basename="risk-rating-limit")

urlpatterns = [
    path("remittance-fee-config/", RemittanceFeeConfigView.as_view(), name="remittance-fee-config"),
    path("", include(router.urls)),
]
