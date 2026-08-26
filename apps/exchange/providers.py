"""汇率外部源 — Mock / Real 可插拔。"""
from __future__ import annotations

import logging
import random
from abc import ABC, abstractmethod
from decimal import Decimal

from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_BASE_RATES = {
    ("USD", "CNY"): Decimal("7.2456"),
    ("CNY", "USD"): Decimal("0.1380"),
    ("USD", "EUR"): Decimal("0.9185"),
    ("EUR", "USD"): Decimal("1.0887"),
    ("USD", "GBP"): Decimal("0.7892"),
    ("GBP", "USD"): Decimal("1.2671"),
    ("USD", "JPY"): Decimal("149.35"),
    ("JPY", "USD"): Decimal("0.006696"),
    ("USD", "HKD"): Decimal("7.8124"),
    ("HKD", "USD"): Decimal("0.1280"),
    ("CNY", "HKD"): Decimal("1.0782"),
    ("HKD", "CNY"): Decimal("0.9275"),
    ("EUR", "CNY"): Decimal("7.8862"),
    ("EUR", "GBP"): Decimal("0.8594"),
    ("EUR", "JPY"): Decimal("162.58"),
    ("GBP", "CNY"): Decimal("9.1753"),
    ("GBP", "JPY"): Decimal("189.12"),
    ("GBP", "HKD"): Decimal("9.8937"),
    ("JPY", "CNY"): Decimal("0.04852"),
    ("HKD", "JPY"): Decimal("19.12"),
}


class BaseFxProvider(ABC):
    @abstractmethod
    def fetch_rates(self, source: str = "Bloomberg") -> list:
        """返回 [{from_currency, to_currency, rate, source}, ...]"""
        ...


class MockFxProvider(BaseFxProvider):
    def fetch_rates(self, source: str = "Bloomberg") -> list:
        logger.info("fx.sync.mock source=%s", source)
        rates = []
        for (f_cur, t_cur), base_rate in DEFAULT_BASE_RATES.items():
            variation = Decimal(str(round(random.uniform(-0.002, 0.002), 6)))
            live_rate = (base_rate * (Decimal("1") + variation)).quantize(Decimal("0.00000001"))
            rates.append({
                "from_currency": f_cur,
                "to_currency": t_cur,
                "rate": live_rate,
                "source": source,
            })
        return rates


class RealFxProvider(BaseFxProvider):
    def fetch_rates(self, source: str = "Bloomberg") -> list:
        api_key = getattr(settings, "FX_API_KEY", "") or ""
        api_url = getattr(settings, "FX_API_URL", "") or ""
        if not api_key and not api_url:
            logger.warning("fx.sync.real blocked: no credentials")
            raise NotImplementedError("FX real provider not configured")
        if not api_url:
            raise NotImplementedError(
                f"FX real provider for {source} requires FX_API_URL "
                "(JSON list of {from_currency,to_currency,rate})"
            )
        import requests
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        resp = requests.get(api_url, headers=headers, params={"source": source}, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        items = payload if isinstance(payload, list) else payload.get("rates", [])
        rates = []
        for item in items:
            rates.append({
                "from_currency": str(item["from_currency"]).upper(),
                "to_currency": str(item["to_currency"]).upper(),
                "rate": Decimal(str(item["rate"])),
                "source": item.get("source", source),
            })
        return rates


def get_fx_provider() -> BaseFxProvider:
    mode = getattr(settings, "BANK_FX_PROVIDER_MODE", "MOCK").upper()
    if mode == "REAL":
        return RealFxProvider()
    return MockFxProvider()
