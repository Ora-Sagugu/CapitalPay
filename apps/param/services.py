from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any
from django.core.paginator import Paginator
from django.db.models import Q
from .models import CoopBank, FeeModel, BankFeeConfig, RiskRatingLimit, RemittanceFeeConfig

PAY_METHOD_TO_CHANNEL = {
    "ONLINE_BANK": "online",
    "WIRE_TRANSFER": "wire",
    "AUTHORIZED": "realtime",
}


def compute_fee_from_model(
    fee_model: FeeModel,
    amount: Decimal,
    override_rate=None,
    override_min=None,
    override_max=None,
) -> Decimal:
    """按手续费模型计算费用。"""
    amount = Decimal(str(amount))
    rate = Decimal(str(override_rate if override_rate is not None else fee_model.base_rate or 0))
    min_fee = Decimal(str(override_min if override_min is not None else fee_model.min_fee or 0))
    max_fee = Decimal(str(override_max if override_max is not None else fee_model.max_fee or 0)) if (
        override_max is not None or fee_model.max_fee is not None
    ) else None

    fee_type = (fee_model.fee_type or "fixed").lower()
    if fee_type == "tiered":
        fee = _tiered_fee(fee_model.tier_config or {}, amount, rate)
    elif fee_type == "mixed":
        fee = min_fee + amount * rate
    else:
        fee = amount * rate

    if min_fee:
        fee = max(fee, min_fee)
    if max_fee:
        fee = min(fee, max_fee)
    return fee.quantize(Decimal("0.01"))


def _tiered_fee(tier_config: dict, amount: Decimal, fallback_rate: Decimal) -> Decimal:
    tiers = tier_config.get("tiers") or tier_config.get("rules") or []
    if not tiers:
        return amount * fallback_rate
    for tier in tiers:
        lo = Decimal(str(tier.get("min", 0)))
        hi = tier.get("max")
        hi_val = Decimal(str(hi)) if hi not in (None, "") else None
        if amount < lo:
            continue
        if hi_val is not None and amount >= hi_val:
            continue
        if "fee" in tier:
            return Decimal(str(tier["fee"]))
        return amount * Decimal(str(tier.get("rate", fallback_rate)))
    return amount * fallback_rate


def resolve_channel_rate(bank_code: str = None, pay_method: str = None) -> Decimal:
    """合作银行手续费配置 → 通道费率。"""
    from django.conf import settings
    if not getattr(settings, "ENABLE_BANKING", True):
        return Decimal("0")
    default_rate = Decimal("0.003")
    channel_type = PAY_METHOD_TO_CHANNEL.get(pay_method or "", "wire")
    today = date.today()
    qs = BankFeeConfig.objects.filter(status=BankFeeConfig.Status.ACTIVE).select_related("fee_model", "bank")
    if bank_code:
        qs = qs.filter(bank__bank_code=bank_code)
    config = qs.filter(channel_type=channel_type).first() or qs.first()
    if config:
        if config.effective_date and config.effective_date > today:
            config = None
        elif config.expiry_date and config.expiry_date < today:
            config = None
    if config:
        if config.override_rate is not None:
            return Decimal(str(config.override_rate))
        return Decimal(str(config.fee_model.base_rate or default_rate))
    if bank_code:
        from apps.routing.models import BankChannel
        ch = BankChannel.objects.filter(bank_code=bank_code).first()
        if ch and ch.fee_rate is not None:
            return Decimal(str(ch.fee_rate))
    return default_rate


def compute_remittance_fee(amount: Decimal, config: Optional[RemittanceFeeConfig] = None) -> Decimal:
    """fee = min(fixed_fee + amount × percent_rate / 100, max_fee)."""
    config = config or RemittanceFeeConfig.get_config()
    amount = Decimal(str(amount))
    fixed = Decimal(str(config.fixed_fee or 0))
    percent = Decimal(str(config.percent_rate or 0))
    max_fee = Decimal(str(config.max_fee or 0))
    fee = fixed + amount * (percent / Decimal("100"))
    fee = min(fee, max_fee)
    return fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ParamService:
    """参数管理服务"""

    @staticmethod
    def list_coop_banks(
        status: Optional[str] = None,
        country: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        queryset = CoopBank.objects.all()
        if status:
            queryset = queryset.filter(status=status)
        if country:
            queryset = queryset.filter(country__icontains=country)
        if search:
            queryset = queryset.filter(
                Q(bank_code__icontains=search) | Q(bank_name__icontains=search) | Q(swift_code__icontains=search)
            )
        total = queryset.count()
        paginator = Paginator(queryset.order_by("bank_code"), page_size)
        page_obj = paginator.get_page(page)
        return {
            "total": total, "page": page, "page_size": page_size,
            "results": list(page_obj.object_list.values())
        }

    @staticmethod
    def create_coop_bank(data: Dict[str, Any]) -> CoopBank:
        return CoopBank.objects.create(**data)

    @staticmethod
    def update_coop_bank(bank_id: str, data: Dict[str, Any]) -> Optional[CoopBank]:
        try:
            bank = CoopBank.objects.get(id=bank_id)
            for key, value in data.items():
                if hasattr(bank, key):
                    setattr(bank, key, value)
            bank.save()
            return bank
        except CoopBank.DoesNotExist:
            return None

    @staticmethod
    def delete_coop_bank(bank_id: str) -> bool:
        try:
            CoopBank.objects.get(id=bank_id).delete()
            return True
        except CoopBank.DoesNotExist:
            return False

    @staticmethod
    def list_fee_models(
        fee_type: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        queryset = FeeModel.objects.all()
        if fee_type:
            queryset = queryset.filter(fee_type=fee_type)
        if status:
            queryset = queryset.filter(status=status)
        if search:
            queryset = queryset.filter(Q(model_name__icontains=search) | Q(model_code__icontains=search))
        total = queryset.count()
        paginator = Paginator(queryset.order_by("model_code"), page_size)
        page_obj = paginator.get_page(page)
        return {
            "total": total, "page": page, "page_size": page_size,
            "results": list(page_obj.object_list.values())
        }

    @staticmethod
    def create_fee_model(data: Dict[str, Any]) -> FeeModel:
        return FeeModel.objects.create(**data)

    @staticmethod
    def update_fee_model(model_id: str, data: Dict[str, Any]) -> Optional[FeeModel]:
        try:
            model = FeeModel.objects.get(id=model_id)
            for key, value in data.items():
                if hasattr(model, key):
                    setattr(model, key, value)
            model.save()
            return model
        except FeeModel.DoesNotExist:
            return None

    @staticmethod
    def delete_fee_model(model_id: str) -> bool:
        try:
            FeeModel.objects.get(id=model_id).delete()
            return True
        except FeeModel.DoesNotExist:
            return False

    @staticmethod
    def list_bank_fee_configs(
        bank_id: Optional[str] = None,
        fee_model_id: Optional[str] = None,
        channel_type: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        queryset = BankFeeConfig.objects.select_related("bank", "fee_model")
        if bank_id:
            queryset = queryset.filter(bank_id=bank_id)
        if fee_model_id:
            queryset = queryset.filter(fee_model_id=fee_model_id)
        if channel_type:
            queryset = queryset.filter(channel_type=channel_type)
        if status:
            queryset = queryset.filter(status=status)
        total = queryset.count()
        paginator = Paginator(queryset.order_by("bank__bank_code", "channel_type"), page_size)
        page_obj = paginator.get_page(page)
        results = []
        for config in page_obj.object_list:
            results.append({
                "id": str(config.id),
                "bank_id": str(config.bank_id),
                "bank_code": config.bank.bank_code,
                "bank_name": config.bank.bank_name,
                "fee_model_id": str(config.fee_model_id),
                "fee_model_name": config.fee_model.model_name,
                "channel_type": config.channel_type,
                "override_rate": config.override_rate,
                "override_min_fee": config.override_min_fee,
                "override_max_fee": config.override_max_fee,
                "status": config.status,
                "effective_date": config.effective_date.isoformat() if config.effective_date else None,
                "expiry_date": config.expiry_date.isoformat() if config.expiry_date else None,
                "created_at": config.created_at.isoformat()
            })
        return {"total": total, "page": page, "page_size": page_size, "results": results}

    @staticmethod
    def create_bank_fee_config(data: Dict[str, Any]) -> BankFeeConfig:
        return BankFeeConfig.objects.create(**data)

    @staticmethod
    def update_bank_fee_config(config_id: str, data: Dict[str, Any]) -> Optional[BankFeeConfig]:
        try:
            config = BankFeeConfig.objects.get(id=config_id)
            for key, value in data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            config.save()
            return config
        except BankFeeConfig.DoesNotExist:
            return None

    @staticmethod
    def delete_bank_fee_config(config_id: str) -> bool:
        try:
            BankFeeConfig.objects.get(id=config_id).delete()
            return True
        except BankFeeConfig.DoesNotExist:
            return False

    RISK_RATING_DEFAULTS = (
        ("LOW", Decimal("10000.00"), 10),
        ("MEDIUM", Decimal("5000.00"), 5),
        ("HIGH", Decimal("1000.00"), 3),
        ("BLOCKED", Decimal("0.00"), 0),
    )
    RISK_LEVEL_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "BLOCKED": 3}

    @classmethod
    def ensure_risk_rating_limits(cls) -> None:
        for risk_level, single, count in cls.RISK_RATING_DEFAULTS:
            daily = single * count
            RiskRatingLimit.objects.get_or_create(
                risk_level=risk_level,
                defaults={
                    "max_single_amount": single,
                    "daily_count": count,
                    "daily_limit": daily,
                },
            )

    @classmethod
    def list_risk_rating_limits(cls):
        cls.ensure_risk_rating_limits()
        rows = list(RiskRatingLimit.objects.all())
        for row in rows:
            expected = row.max_single_amount * row.daily_count
            if row.daily_limit != expected:
                row.sync_daily_limit()
                row.save(update_fields=["daily_limit", "updated_at"])
        rows.sort(key=lambda row: cls.RISK_LEVEL_ORDER.get(row.risk_level, 99))
        return rows

    @staticmethod
    def update_risk_rating_limit(limit_id: str, data: Dict[str, Any]) -> Optional[RiskRatingLimit]:
        try:
            row = RiskRatingLimit.objects.get(id=limit_id)
        except RiskRatingLimit.DoesNotExist:
            return None
        for key in ("max_single_amount", "daily_count"):
            if key in data:
                setattr(row, key, data[key])
        row.sync_daily_limit()
        row.save()
        return row

    @staticmethod
    def update_remittance_fee_config(data: Dict[str, Any], updated_by: str = "") -> RemittanceFeeConfig:
        config = RemittanceFeeConfig.get_config()
        for key in ("fixed_fee", "percent_rate", "max_fee"):
            if key in data:
                setattr(config, key, data[key])
        if updated_by:
            config.updated_by = updated_by
        config.save()
        return config
