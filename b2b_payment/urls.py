"""Root URL configuration for CapitalPay."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from rest_framework.permissions import AllowAny
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from apps.payment.urls import urlpatterns_merchant as payment_merchant_urls
from apps.payment import views_cashier

urlpatterns = [
    path("admin/", admin.site.urls),
    # ── OpenAPI (对外接口，HMAC 鉴权) ──
    path("api/v1/", include("apps.openapi.urls")),
    path("api/v1/", include(payment_merchant_urls)),
    path("api/v1/cashier/orders/<str:order_no>/", views_cashier.cashier_order, name="cashier-order"),
    path("api/v1/cashier/orders/<str:order_no>/pay/", views_cashier.cashier_pay, name="cashier-pay"),
    # ── 运营管理端 (JWT 鉴权) ──
    path("api/v1/admin/", include("apps.merchant.urls_admin")),
    path("api/v1/admin/", include("apps.payment.urls_admin")),
    path("api/v1/admin/", include("apps.reconciliation.urls")),
    path("api/v1/admin/", include("apps.settlement.urls")),
    path("api/v1/admin/", include("apps.account.urls")),
    path("api/v1/admin/", include("apps.report.urls")),
    path("api/v1/admin/", include("apps.rbac.urls")),
    path("api/v1/admin/", include("apps.core.urls")),
    path("api/v1/admin/", include("apps.agent.urls")),
    path("api/v1/admin/", include("apps.compliance.urls")),
    path("api/v1/admin/", include("apps.routing.urls")),
    path("api/v1/admin/", include("apps.param.urls")),
    path("api/v1/admin/", include("apps.adjustment.urls")),
    path("api/v1/admin/", include("apps.exchange.urls")),
    # ── 用户端 (JWT 鉴权) ──
    path("api/v1/user/", include("apps.user_portal.urls")),
    path("api/v1/admin/", include("apps.user_portal.urls_admin")),
    # ── API 文档 (Swagger / ReDoc) ──
    path("api/schema/", SpectacularAPIView.as_view(
        authentication_classes=[], permission_classes=[AllowAny]
    ), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(
        url_name="schema", authentication_classes=[], permission_classes=[AllowAny]
    ), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(
        url_name="schema", authentication_classes=[], permission_classes=[AllowAny]
    ), name="redoc"),
]

# ── Media serving (development only) ──
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
