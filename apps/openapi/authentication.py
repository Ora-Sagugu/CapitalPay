"""OpenAPI 服务 — 对外商户接口。

功能清单对应:
    - OpenAPI服务 (PC, H5, SDK) - 商户平台对接
    - 预下单 + 支付查询 + 退款
"""

import hmac, hashlib, time
from django.core.cache import cache
from rest_framework import authentication, exceptions
from rest_framework.permissions import BasePermission
from apps.merchant.services import MerchantService


class HMACAuthentication(authentication.BaseAuthentication):
    """HMAC-SHA256 签名鉴权。

    Headers:
        X-Api-Key: 商户 API Key
        X-Timestamp: Unix 时间戳 (秒)
        X-Nonce: 随机数 (防重放)
        X-Signature: 签名
    """

    TIMEOUT_SECONDS = 300  # 5 分钟有效期

    def authenticate_header(self, request):
        return "HMAC"

    def authenticate(self, request):
        api_key = request.headers.get("X-Api-Key")
        timestamp = request.headers.get("X-Timestamp")
        signature = request.headers.get("X-Signature")
        nonce = request.headers.get("X-Nonce")

        if not all([api_key, timestamp, signature, nonce]):
            raise exceptions.NotAuthenticated("The HMAC authentication headers are incomplete")

        # ── 1. 防重放: 时间戳检查 ──
        try:
            ts = int(timestamp)
        except (ValueError, TypeError):
            raise exceptions.AuthenticationFailed("The timestamp is malformed")

        now_ts = int(time.time())
        if abs(now_ts - ts) > self.TIMEOUT_SECONDS:
            raise exceptions.AuthenticationFailed("The request has expired")

        # ── 2. 防重放: nonce 去重 ──
        nonce_key = f"api_nonce:{api_key}:{nonce}"
        if not cache.add(nonce_key, "1", timeout=self.TIMEOUT_SECONDS):
            raise exceptions.AuthenticationFailed("The request is a duplicate")

        # ── 3. 查询商户，未命中再查代理 ──
        merchant_service = MerchantService()
        merchant = None
        try:
            merchant = merchant_service.get_by_api_key(api_key)
        except Exception:
            merchant = None

        agent = None
        if merchant is None:
            from django.conf import settings
            if not getattr(settings, "ENABLE_AGENTS", True):
                raise exceptions.AuthenticationFailed("The API key is invalid")
            from apps.agent.models import Agent
            agent = Agent.objects.filter(api_key=api_key, is_deleted=False).first()
            if not agent:
                raise exceptions.AuthenticationFailed("The API key is invalid")
            secret = agent.api_secret or ""
        else:
            secret = merchant.api_secret or ""

        if merchant is not None and merchant.status != "ACTIVE":
            raise exceptions.AuthenticationFailed("The customer is not presently authorised to use the Open API")
        if agent is not None and getattr(agent, "status", "") != "ACTIVE":
            raise exceptions.AuthenticationFailed("The agent is not presently authorised to use the Open API")

        # ── 4. 验签 ──
        try:
            self._verify_signature(request, api_key, timestamp, nonce, signature, secret)
        except exceptions.AuthenticationFailed:
            raise

        if merchant is not None:
            request.merchant = merchant
            request.agent = None
            return (None, merchant)

        request.merchant = None
        request.agent = agent
        return (None, agent)

    def _verify_signature(self, request, api_key, timestamp, nonce, signature, secret):
        """构造签名字符串并验签。"""
        # 排序查询参数
        query_string = ""
        if request.GET:
            sorted_keys = sorted(request.GET.keys())
            query_string = "&".join(f"{k}={request.GET[k]}" for k in sorted_keys)

        body = request.body.decode("utf-8") if request.body else ""

        sign_str = f"{api_key}{timestamp}{nonce}{request.method}{request.path}"
        if query_string:
            sign_str += f"?{query_string}"
        if body:
            sign_str += body

        expected = hmac.new(
            secret.encode(), sign_str.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise exceptions.AuthenticationFailed("Signature verification failed")


class HasHMACPrincipal(BasePermission):
    """要求 HMAC 认证确实解析出商户或代理商主体。"""

    message = "HMAC authentication failed"

    def has_permission(self, request, view):
        return bool(
            request.auth
            and (
                getattr(request, "merchant", None)
                or getattr(request, "agent", None)
            )
        )
