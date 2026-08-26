"""OpenAPI 服务 — 对外商户接口。

功能清单对应:
    - OpenAPI服务 (PC, H5, SDK) - 商户平台对接
    - 预下单 + 支付查询 + 退款
"""

import hmac, hashlib, time
from django.conf import settings
from django.core.cache import cache
from rest_framework import authentication, exceptions
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

    def authenticate(self, request):
        api_key = request.headers.get("X-Api-Key")
        timestamp = request.headers.get("X-Timestamp")
        signature = request.headers.get("X-Signature")
        nonce = request.headers.get("X-Nonce")

        if not all([api_key, timestamp, signature, nonce]):
            return None  # 不强制鉴权，由视图决定

        # ── 1. 防重放: 时间戳检查 ──
        try:
            ts = int(timestamp)
        except (ValueError, TypeError):
            raise exceptions.AuthenticationFailed("时间戳格式错误")

        now_ts = int(time.time())
        if abs(now_ts - ts) > self.TIMEOUT_SECONDS:
            raise exceptions.AuthenticationFailed("请求已过期")

        # ── 2. 防重放: nonce 去重 ──
        nonce_key = f"api_nonce:{api_key}:{nonce}"
        if not cache.add(nonce_key, "1", timeout=self.TIMEOUT_SECONDS):
            raise exceptions.AuthenticationFailed("重复请求")

        # ── 3. 查询商户 ──
        merchant_service = MerchantService()
        try:
            merchant = merchant_service.get_by_api_key(api_key)
        except Exception:
            raise exceptions.AuthenticationFailed("API Key 无效")

        secret = merchant.api_secret

        # ── 4. 验签 ──
        try:
            self._verify_signature(request, api_key, timestamp, nonce, signature, secret)
        except exceptions.AuthenticationFailed:
            raise

        return (None, merchant)

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
            raise exceptions.AuthenticationFailed("签名验证失败")
