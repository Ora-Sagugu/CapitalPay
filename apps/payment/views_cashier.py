"""收银台 — 公开查询与 Mock 支付确认。"""
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt

from apps.core.exceptions import BusinessException
from apps.payment.models import PaymentOrder
from apps.payment.services.payment import PaymentConfirmService
from apps.payment.gateway import BankGatewayRouter


def _get_order(order_no, uin=None):
    order = PaymentOrder.objects.filter(order_no=order_no, is_deleted=False).select_related("merchant").first()
    if not order:
        return None, Response({"code": "ORDER_NOT_FOUND"}, status=404)
    if uin and order.unique_identification_no != uin:
        return None, Response({"code": "UIN_MISMATCH"}, status=403)
    return order, None


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@csrf_exempt
def cashier_order(request, order_no):
    uin = request.query_params.get("uin") or ""
    order, err = _get_order(order_no, uin or None)
    if err:
        return err
    return Response({
        "order_no": order.order_no,
        "merchant_name": order.merchant.merchant_name,
        "amount": str(order.amount),
        "fee_amount": str(order.fee_amount),
        "currency": order.currency,
        "status": order.status,
        "pay_method": order.pay_method,
        "unique_identification_no": order.unique_identification_no,
        "expire_at": order.expire_at.isoformat() if order.expire_at else None,
    })


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@csrf_exempt
def cashier_pay(request, order_no):
    uin = request.data.get("uin") or request.query_params.get("uin")
    order, err = _get_order(order_no, uin)
    if err:
        return err
    if order.status not in (
        PaymentOrder.OrderStatus.PENDING_PAY,
        PaymentOrder.OrderStatus.PRE_CREATE,
    ):
        return Response({"code": "ORDER_STATUS_INVALID", "status": order.status}, status=400)

    if order.pay_method == PaymentOrder.PayMethod.WIRE_TRANSFER:
        return Response({
            "code": "WIRE_INSTRUCTIONS",
            "message": "Remit funds to the platform nostro account, citing the UIN in the payment narrative",
            "unique_identification_no": order.unique_identification_no,
            "amount": str(order.amount),
        })

    gateway = BankGatewayRouter.get_gateway(order.bank_code)
    result = gateway.pay(order)
    if not result.get("success"):
        return Response({"code": "PAY_FAILED", "message": result.get("message", "")}, status=400)

    try:
        PaymentConfirmService()._confirm_payment(
            order,
            {"txn_id": result.get("txn_id") or f"CASHIER_{order.order_no}", "amount": order.amount},
        )
    except BusinessException as e:
        return Response({"code": e.code, "message": e.message}, status=e.http_status)

    order.refresh_from_db()
    return Response({
        "code": "SUCCESS",
        "status": order.status,
        "order_no": order.order_no,
    }, status=status.HTTP_200_OK)
