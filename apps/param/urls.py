from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CoopBankViewSet, FeeModelViewSet, BankFeeConfigViewSet

router = DefaultRouter()
router.register(r"coop-banks", CoopBankViewSet, basename="coop-bank")
router.register(r"fee-models", FeeModelViewSet, basename="fee-model")
router.register(r"bank-fee-configs", BankFeeConfigViewSet, basename="bank-fee-config")

urlpatterns = [
    path("", include(router.urls)),
]
