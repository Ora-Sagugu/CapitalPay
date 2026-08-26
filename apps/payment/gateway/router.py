"""银行网关路由 — 按 bank_code / 环境模式返回实例。"""
from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings

from .base import BaseBankGateway
from .mock import MockBankGateway
from .real import RealBankGateway

logger = logging.getLogger(__name__)


class BankGatewayRouter:
    """银行网关路由。"""

    _gateways = {}
    _bootstrapped = False

    @classmethod
    def bootstrap(cls):
        if cls._bootstrapped:
            return
        mode = getattr(settings, "BANK_GATEWAY_MODE", "MOCK").upper()
        codes = getattr(settings, "BANK_CODES", ["MOCK"])
        cls._gateways = {}
        for code in codes:
            code = (code or "MOCK").upper()
            if mode == "MOCK" or code == "MOCK":
                gw = MockBankGateway()
                gw.bank_code = code
                if code != "MOCK":
                    gw.bank_name = f"模拟-{code}"
                cls._gateways[code] = gw
            else:
                cls._gateways[code] = RealBankGateway(code)
        if "MOCK" not in cls._gateways:
            cls._gateways["MOCK"] = MockBankGateway()
        cls._bootstrapped = True
        logger.info("bank.router bootstrapped mode=%s codes=%s", mode, list(cls._gateways))

    @classmethod
    def register(cls, bank_code: str, gateway: BaseBankGateway):
        cls._gateways[bank_code] = gateway

    @classmethod
    def get_gateway(cls, bank_code: Optional[str] = None) -> BaseBankGateway:
        cls.bootstrap()
        mode = getattr(settings, "BANK_GATEWAY_MODE", "MOCK").upper()
        if not bank_code:
            if mode == "MOCK":
                return cls._gateways.get("MOCK") or MockBankGateway()
            raise ValueError("银行网关未指定 bank_code")
        gateway = cls._gateways.get(bank_code)
        if gateway is None:
            if mode == "MOCK":
                logger.warning("bank.router fallback to MOCK for unknown code=%s", bank_code)
                return cls._gateways.get("MOCK") or MockBankGateway()
            raise ValueError(f"银行网关未注册: {bank_code}")
        return gateway

    @classmethod
    def list_banks(cls) -> list:
        cls.bootstrap()
        return [
            {"bank_code": code, "bank_name": gw.name()}
            for code, gw in cls._gateways.items()
        ]
