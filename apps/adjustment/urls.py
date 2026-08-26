from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AdjustmentApplicationViewSet

router = DefaultRouter()
router.register(r"applications", AdjustmentApplicationViewSet, basename="adjustment-application")

urlpatterns = [
    path("", include(router.urls)),
]
