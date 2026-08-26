from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ExchangeRateViewSet

router = DefaultRouter()
router.register("exchange-rates", ExchangeRateViewSet, basename="exchange-rate")

urlpatterns = [
    path("", include(router.urls)),
]
