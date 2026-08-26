"""OpenAPI — URL 路由。"""
from django.urls import path
from . import views

urlpatterns = [
    # ── 支付接口 ──
    path("payment/pre-order/", views.pre_order, name="api-pre-order"),
    path("payment/orders/", views.order_query, name="api-order-list"),

    # ── 单笔订单 ──
    path("payment/orders/<str:order_no>/", views.order_query, name="api-order-detail"),
    path("payment/orders/<str:order_no>/close/", views.order_query, name="api-order-close"),

    # ── 退款接口 ──
    path("refund/apply/", views.refund_apply, name="api-refund-apply"),
    path("refund/query/", views.refund_query, name="api-refund-query"),
]
