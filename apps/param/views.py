from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from apps.rbac.permissions import RequiresFeature
from .services import ParamService
from .serializers import (
    CoopBankSerializer, CoopBankListSerializer, FeeModelSerializer,
    BankFeeConfigSerializer, RiskRatingLimitSerializer, RemittanceFeeConfigSerializer,
)
from .models import CoopBank, FeeModel, BankFeeConfig, RiskRatingLimit, RemittanceFeeConfig


class CoopBankViewSet(RequiresFeature, viewsets.ViewSet):
    """合作银行管理"""
    permission_classes = [IsAuthenticated]
    feature_code = "feature:params"

    def list(self, request):
        status_param = request.query_params.get("status")
        country = request.query_params.get("country")
        search = request.query_params.get("search")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        data = ParamService.list_coop_banks(status_param, country, search, page, page_size)
        return Response(data)

    def create(self, request):
        ser = CoopBankSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        bank = ParamService.create_coop_bank(ser.validated_data)
        return Response(CoopBankSerializer(bank).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        try:
            bank = CoopBank.objects.get(id=pk)
            return Response(CoopBankSerializer(bank).data)
        except CoopBank.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    def update(self, request, pk=None):
        ser = CoopBankSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        bank = ParamService.update_coop_bank(pk, ser.validated_data)
        if bank:
            return Response(CoopBankSerializer(bank).data)
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, pk=None):
        if ParamService.delete_coop_bank(pk):
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)


class FeeModelViewSet(RequiresFeature, viewsets.ViewSet):
    """手续费模型管理"""
    permission_classes = [IsAuthenticated]
    feature_code = "feature:params"

    def list(self, request):
        fee_type = request.query_params.get("fee_type")
        status_param = request.query_params.get("status")
        search = request.query_params.get("search")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        data = ParamService.list_fee_models(fee_type, status_param, search, page, page_size)
        return Response(data)

    def create(self, request):
        ser = FeeModelSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        model = ParamService.create_fee_model(ser.validated_data)
        return Response(FeeModelSerializer(model).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        try:
            model = FeeModel.objects.get(id=pk)
            return Response(FeeModelSerializer(model).data)
        except FeeModel.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    def update(self, request, pk=None):
        ser = FeeModelSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        model = ParamService.update_fee_model(pk, ser.validated_data)
        if model:
            return Response(FeeModelSerializer(model).data)
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, pk=None):
        if ParamService.delete_fee_model(pk):
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)


class BankFeeConfigViewSet(RequiresFeature, viewsets.ViewSet):
    """银行手续费配置管理"""
    permission_classes = [IsAuthenticated]
    feature_code = "feature:params"

    def list(self, request):
        bank_id = request.query_params.get("bank_id")
        fee_model_id = request.query_params.get("fee_model_id")
        channel_type = request.query_params.get("channel_type")
        status_param = request.query_params.get("status")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        data = ParamService.list_bank_fee_configs(bank_id, fee_model_id, channel_type, status_param, page, page_size)
        return Response(data)

    def create(self, request):
        ser = BankFeeConfigSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        config = ParamService.create_bank_fee_config(ser.validated_data)
        return Response(BankFeeConfigSerializer(config).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        try:
            config = BankFeeConfig.objects.select_related("bank", "fee_model").get(id=pk)
            return Response(BankFeeConfigSerializer(config).data)
        except BankFeeConfig.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    def update(self, request, pk=None):
        ser = BankFeeConfigSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        config = ParamService.update_bank_fee_config(pk, ser.validated_data)
        if config:
            return Response(BankFeeConfigSerializer(config).data)
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, pk=None):
        if ParamService.delete_bank_fee_config(pk):
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)


class RiskRatingLimitViewSet(RequiresFeature, viewsets.ViewSet):
    """风险等级默认限额：固定四档，仅允许修改限额字段。"""
    permission_classes = [IsAuthenticated]
    feature_code = "feature:risk_rating"

    def list(self, request):
        rows = ParamService.list_risk_rating_limits()
        data = RiskRatingLimitSerializer(rows, many=True).data
        return Response({"total": len(data), "results": data})

    def retrieve(self, request, pk=None):
        try:
            row = RiskRatingLimit.objects.get(id=pk)
            return Response(RiskRatingLimitSerializer(row).data)
        except RiskRatingLimit.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    def update(self, request, pk=None):
        return self._save(request, pk)

    def partial_update(self, request, pk=None):
        return self._save(request, pk)

    def _save(self, request, pk):
        ser = RiskRatingLimitSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        row = ParamService.update_risk_rating_limit(pk, ser.validated_data)
        if row:
            return Response(RiskRatingLimitSerializer(row).data)
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)


class RemittanceFeeConfigView(RequiresFeature, APIView):
    """全局汇款手续费单例：GET / PUT /api/v1/admin/remittance-fee-config/"""
    permission_classes = [IsAuthenticated]
    feature_code = "feature:remittance_fees"

    def get(self, request):
        config = RemittanceFeeConfig.get_config()
        return Response(RemittanceFeeConfigSerializer(config).data)

    def put(self, request):
        config = RemittanceFeeConfig.get_config()
        ser = RemittanceFeeConfigSerializer(config, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        updated = ParamService.update_remittance_fee_config(
            ser.validated_data,
            updated_by=getattr(request.user, "username", "") or "admin",
        )
        return Response(RemittanceFeeConfigSerializer(updated).data)
