"""OpenAPI — 对外接口 Views。

提供商户对接的预下单、订单查询、退款等接口。
使用 HMAC 签名鉴权。
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from django.views.decorators.csrf import csrf_exempt

from .authentication import HMACAuthentication
from apps.core.exceptions import BusinessException, ErrorCode
from apps.payment.models import PaymentOrder, RefundOrder
from apps.payment.serializers import (
    PreOrderRequestSerializer, PreOrderResponseSerializer,
    RefundRequestSerializer, RefundOrderSerializer,
    PaymentOrderSerializer, PaymentOrderListSerializer,
)
from apps.payment.services.pre_order import PreOrderService
from apps.payment.services.refund import RefundService


@api_view(["POST"])
@authentication_classes([HMACAuthentication])
@permission_classes([AllowAny])
@csrf_exempt
def pre_order(request):
    """预下单接口。

    POST /api/v1/payment/pre-order/
    Headers: X-Api-Key, X-Timestamp, X-Nonce, X-Signature
    Body:   merchant_no, merchant_order_no, amount, pay_method, ...

    Returns:
        {order_no, unique_identification_no, amount, fee_amount, status, ...}
    """
    # merchant 从 HMAC 鉴权中获取
    merchant = getattr(request, "merchant", None) if hasattr(request, "merchant") else None
    if not merchant:
        return Response({"code": "AUTH_FAILED", "message": "鉴权失败"}, status=401)

    serializer = PreOrderRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    data = serializer.validated_data
    # 覆盖 merchant_no 为鉴权得到的商户
    data["merchant_no"] = merchant.merchant_no

    service = PreOrderService()
    try:
        order = service.create_pre_order(
            merchant_no=data["merchant_no"],
            merchant_order_no=data["merchant_order_no"],
            amount=data["amount"],
            currency=data.get("currency", "CNY"),
            pay_method=data["pay_method"],
            bank_code=data.get("bank_code"),
            user_id=data.get("user_id"),
            notify_url=data.get("notify_url"),
            idempotency_key=data.get("idempotency_key"),
        )
    except BusinessException as e:
        return Response({"code": e.code, "message": e.message}, status=e.http_status)

    return Response({
        "code": "SUCCESS",
        "order_no": order.order_no,
        "unique_identification_no": order.unique_identification_no,
        "amount": str(order.amount),
        "fee_amount": str(order.fee_amount),
        "settle_amount": str(order.settle_amount),
        "status": order.status,
        "expire_at": order.expire_at.isoformat(),
        "created_at": order.created_at.isoformat(),
    }, status=status.HTTP_201_CREATED)


@api_view(["GET", "POST"])
@authentication_classes([HMACAuthentication])
@permission_classes([AllowAny])
@csrf_exempt
def order_query(request, order_no=None):
    """订单查询接口。

    GET /api/v1/payment/orders/                     (列表)
    GET /api/v1/payment/orders/{order_no}/          (详情)
    POST /api/v1/payment/orders/{order_no}/close/   (关单)
    """
    merchant = getattr(request, "merchant", None) if hasattr(request, "merchant") else None
    if not merchant:
        return Response({"code": "AUTH_FAILED", "message": "鉴权失败"}, status=401)

    if request.method == "GET" and not order_no:
        # 订单列表
        merchant_order_no = request.query_params.get("merchant_order_no")
        orders = PaymentOrder.objects.filter(
            merchant=merchant, is_deleted=False
        )
        if merchant_order_no:
            orders = orders.filter(merchant_order_no=merchant_order_no)
        orders = orders.order_by("-created_at")[:50]

        return Response({
            "code": "SUCCESS",
            "count": orders.count(),
            "results": [
                {
                    "order_no": o.order_no,
                    "merchant_order_no": o.merchant_order_no,
                    "amount": str(o.amount),
                    "fee_amount": str(o.fee_amount),
                    "status": o.status,
                    "pay_method": o.pay_method,
                    "created_at": o.created_at.isoformat(),
                }
                for o in orders
            ],
        })

    if not order_no:
        return Response({"code": "ORDER_NO_REQUIRED"}, status=400)

    try:
        order = PaymentOrder.objects.get(
            order_no=order_no, merchant=merchant, is_deleted=False
        )
    except PaymentOrder.DoesNotExist:
        return Response({"code": "ORDER_NOT_FOUND"}, status=404)

    if request.method == "GET":
        return Response({
            "code": "SUCCESS",
            "order_no": order.order_no,
            "merchant_order_no": order.merchant_order_no,
            "amount": str(order.amount),
            "currency": order.currency,
            "fee_amount": str(order.fee_amount),
            "settle_amount": str(order.settle_amount),
            "status": order.status,
            "pay_method": order.pay_method,
            "unique_identification_no": order.unique_identification_no,
            "pay_received_at": order.pay_received_at.isoformat() if order.pay_received_at else None,
            "settled_at": order.settled_at.isoformat() if order.settled_at else None,
            "created_at": order.created_at.isoformat(),
            "expire_at": order.expire_at.isoformat(),
        })

    if request.method == "POST":
        from apps.payment.services.close_order import CloseOrderService
        service = CloseOrderService()
        try:
            service.close_order(order)
        except BusinessException as e:
            return Response({"code": e.code, "message": e.message}, status=e.http_status)

        return Response({"code": "SUCCESS", "message": "订单已关闭"})


@api_view(["POST"])
@authentication_classes([HMACAuthentication])
@permission_classes([AllowAny])
@csrf_exempt
def refund_apply(request):
    """退款申请接口。

    POST /api/v1/refund/apply/
    Body: order_no, refund_amount, reason
    """
    merchant = getattr(request, "merchant", None) if hasattr(request, "merchant") else None
    if not merchant:
        return Response({"code": "AUTH_FAILED", "message": "鉴权失败"}, status=401)

    serializer = RefundRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        order = PaymentOrder.objects.get(
            order_no=data["order_no"], merchant=merchant, is_deleted=False
        )
    except PaymentOrder.DoesNotExist:
        return Response({"code": "ORDER_NOT_FOUND"}, status=404)

    service = RefundService()
    try:
        refund = service.request_refund(
            payment_order=order,
            refund_amount=data["refund_amount"],
            reason=data["reason"],
            idempotency_key=data.get("idempotency_key"),
        )
    except BusinessException as e:
        return Response({"code": e.code, "message": e.message}, status=e.http_status)

    return Response({
        "code": "SUCCESS",
        "refund_no": refund.refund_no,
        "refund_amount": str(refund.refund_amount),
        "refund_fee_rate": str(refund.refund_fee_rate),
        "refund_fee_amount": str(refund.refund_fee_amount),
        "status": refund.status,
        "created_at": refund.created_at.isoformat(),
    }, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@authentication_classes([HMACAuthentication])
@permission_classes([AllowAny])
@csrf_exempt
def refund_query(request):
    """退款查询接口。

    GET /api/v1/refund/query/?order_no=xxx
    """
    merchant = getattr(request, "merchant", None) if hasattr(request, "merchant") else None
    if not merchant:
        return Response({"code": "AUTH_FAILED", "message": "鉴权失败"}, status=401)

    order_no = request.query_params.get("order_no")
    if not order_no:
        return Response({"code": "ORDER_NO_REQUIRED"}, status=400)

    refunds = RefundOrder.objects.filter(
        payment_order__order_no=order_no,
        payment_order__merchant=merchant,
        is_deleted=False,
    ).select_related("payment_order")

    return Response({
        "code": "SUCCESS",
        "count": refunds.count(),
        "results": [{
            "refund_no": r.refund_no,
            "refund_amount": str(r.refund_amount),
            "refund_fee_rate": str(r.refund_fee_rate),
            "refund_fee_amount": str(r.refund_fee_amount),
            "refund_reason": r.refund_reason,
            "status": r.status,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            "refunded_at": r.refunded_at.isoformat() if r.refunded_at else None,
            "created_at": r.created_at.isoformat(),
        } for r in refunds],
    })
