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

    # ── 商户清算查询 / 下载 ──
    path("merchant/pending-funds/", views.merchant_pending_funds, name="api-merchant-pending-funds"),
    path("merchant/settled-funds/", views.merchant_settled_funds, name="api-merchant-settled-funds"),
    path("merchant/settled-funds/export/", views.merchant_settled_funds_export, name="api-merchant-settled-funds-export"),
    path("merchant/settled-orders/export/", views.merchant_settled_orders_export, name="api-merchant-settled-orders-export"),

    # ── 代理 PRN 签发 ──
    path("agent/prn/apply/", views.agent_prn_apply, name="api-agent-prn-apply"),
    path("agent/prn/<str:prn_code>/", views.agent_prn_query, name="api-agent-prn-query"),
]
