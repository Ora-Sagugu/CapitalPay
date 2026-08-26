from typing import Optional, Dict, Any
from django.core.paginator import Paginator
from django.db.models import Q
from .models import CoopBank, FeeModel, BankFeeConfig


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
                Q(bank_name__icontains=search) | Q(bank_code__icontains=search) | Q(swift_code__icontains=search)
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
                "bank_name": config.bank.bank_name,
                "bank_code": config.bank.bank_code,
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
