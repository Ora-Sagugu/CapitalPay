"""统一业务异常和 DRF 异常处理。"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


class BusinessException(Exception):
    """业务异常 — 携带错误码和 HTTP 状态码。"""

    def __init__(self, code: str, message: str = "", http_status: int = 400):
        self.code = code
        self.message = message or code
        self.http_status = http_status
        super().__init__(message)


# ── 预定义业务错误码 ──

class ErrorCode:
    MERCHANT_NOT_FOUND = "MERCHANT_NOT_FOUND"
    MERCHANT_INACTIVE = "MERCHANT_INACTIVE"
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
    ORDER_STATUS_INVALID = "ORDER_STATUS_INVALID"
    ORDER_ALREADY_CLOSED = "ORDER_ALREADY_CLOSED"
    ORDER_EXPIRED = "ORDER_EXPIRED"
    ORDER_AMOUNT_MISMATCH = "ORDER_AMOUNT_MISMATCH"
    REFUND_EXCEED_AMOUNT = "REFUND_EXCEED_AMOUNT"
    DUPLICATE_REQUEST = "DUPLICATE_REQUEST"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    FEE_NOT_CONFIGURED = "FEE_NOT_CONFIGURED"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    RECONCILIATION_IN_PROGRESS = "RECONCILIATION_IN_PROGRESS"


def custom_exception_handler(exc, context):
    """DRF 自定义异常处理 — 统一返回格式。"""
    response = exception_handler(exc, context)

    if response is not None:
        return response

    if isinstance(exc, BusinessException):
        return Response(
            data={
                "code": exc.code,
                "message": exc.message,
            },
            status=exc.http_status,
        )

    # 未预期异常
    return Response(
        data={
            "code": "INTERNAL_ERROR",
            "message": "系统内部错误",
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
