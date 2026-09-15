"""统一业务异常和 DRF 异常处理。"""
import logging
import uuid

from rest_framework import exceptions as drf_exceptions
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


class BusinessException(Exception):
    """业务异常 — 携带错误码和 HTTP 状态码。"""

    def __init__(
        self,
        code: str,
        message: str = "",
        http_status: int = 400,
        field: str = "",
        details: dict | None = None,
    ):
        self.code = code
        self.message = message or code
        self.http_status = http_status
        self.field = field
        self.details = details or {}
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
    NO_PAYOUT_BANK = "NO_PAYOUT_BANK"
    PAYOUT_BANK_INVALID = "PAYOUT_BANK_INVALID"
    PAYOUT_BANK_INSUFFICIENT = "PAYOUT_BANK_INSUFFICIENT"
    AGENT_PAYOUT_REQUEST_REQUIRED = "AGENT_PAYOUT_REQUEST_REQUIRED"
    RECONCILIATION_IN_PROGRESS = "RECONCILIATION_IN_PROGRESS"


def _request_id(context) -> str:
    request = context.get("request") if context else None
    if request:
        supplied = request.headers.get("X-Request-ID", "").strip()
        if supplied:
            return supplied[:128]
    return uuid.uuid4().hex


def _first_field(data, prefix="") -> str:
    if isinstance(data, dict):
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            nested = _first_field(value, path)
            return nested or path
    if isinstance(data, list) and data:
        return _first_field(data[0], prefix)
    return prefix


def custom_exception_handler(exc, context):
    """DRF 自定义异常处理 — 统一返回格式。"""
    # 惰性导入，避免 DEFAULT_AUTHENTICATION_CLASSES 初始化时形成 DRF 导入环。
    from rest_framework.views import exception_handler

    request_id = _request_id(context)

    if isinstance(exc, BusinessException):
        response = Response(
            data={
                "code": exc.code,
                "message": exc.message,
                "field": exc.field or None,
                "details": exc.details,
                "request_id": request_id,
            },
            status=exc.http_status,
        )
        response["X-Request-ID"] = request_id
        return response

    response = exception_handler(exc, context)
    if response is not None:
        if isinstance(exc, drf_exceptions.ValidationError):
            code = "VALIDATION_ERROR"
            field = _first_field(response.data)
            message = f"Validation failed for {field}" if field else "Validation failed"
            details = {"fields": response.data}
        elif isinstance(exc, (drf_exceptions.NotAuthenticated, drf_exceptions.AuthenticationFailed)):
            code = "UNAUTHENTICATED"
            field = ""
            message = "Authentication credentials are invalid or the session has expired"
            details = {}
        elif isinstance(exc, drf_exceptions.PermissionDenied):
            code = "PERMISSION_DENIED"
            field = ""
            message = "The authenticated principal is not authorised for this operation"
            details = {}
        elif isinstance(exc, drf_exceptions.NotFound):
            code = "NOT_FOUND"
            field = ""
            message = "The requested resource does not exist"
            details = {}
        else:
            code = "API_ERROR"
            field = ""
            message = "The request could not be processed"
            details = {}
        response.data = {
            "code": code,
            "message": message,
            "field": field or None,
            "details": details,
            "request_id": request_id,
        }
        response["X-Request-ID"] = request_id
        return response

    # 未预期异常
    logger.exception("Unhandled API error request_id=%s", request_id, exc_info=True)
    response = Response(
        data={
            "code": "INTERNAL_ERROR",
            "message": "An internal error occurred while processing the request",
            "field": None,
            "details": {},
            "request_id": request_id,
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    response["X-Request-ID"] = request_id
    return response
