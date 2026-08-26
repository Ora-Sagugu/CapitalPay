"""短信发送适配 — MOCK（开发）/ LOG / REAL（需配置）。"""
from __future__ import annotations

import logging
import random

from django.conf import settings

logger = logging.getLogger(__name__)


def send_sms(phone: str, message: str) -> dict:
    """发送短信。默认 MOCK：不外发，返回成功。

    SMS_PROVIDER_MODE:
      - MOCK: 开发固定码由业务层决定，本函数仅记录
      - LOG: 记录日志，视为已发送
      - REAL: 需配置 SMS_API_URL / SMS_API_KEY，否则显式失败
    """
    mode = getattr(settings, "SMS_PROVIDER_MODE", "MOCK").upper()
    if mode in ("MOCK", "LOG"):
        logger.info("sms.%s phone=%s msg=%s", mode.lower(), phone, message[:80])
        return {"success": True, "mode": mode, "provider_msg_id": f"mock-{random.randint(1000,9999)}"}

    api_url = getattr(settings, "SMS_API_URL", "") or ""
    api_key = getattr(settings, "SMS_API_KEY", "") or ""
    if not api_url or not api_key:
        logger.warning("sms.real blocked: credentials missing")
        raise NotImplementedError("SMS real provider not configured")

    import requests
    resp = requests.post(
        api_url,
        json={"phone": phone, "message": message},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json() if resp.content else {}
    return {"success": True, "mode": "REAL", "provider_msg_id": data.get("id", "")}
