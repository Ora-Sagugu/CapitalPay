from typing import Optional
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .services import ParamService
from .serializers import CoopBankSerializer, CoopBankListSerializer, FeeModelSerializer, BankFeeConfigSerializer
from .models import CoopBank, FeeModel, BankFeeConfig


class CoopBankViewSet(viewsets.ViewSet):
    """合作银行管理"""
    permission_classes = [AllowAny]

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


class FeeModelViewSet(viewsets.ViewSet):
    """手续费模型管理"""
    permission_classes = [AllowAny]

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


class BankFeeConfigViewSet(viewsets.ViewSet):
    """银行手续费配置管理"""
    permission_classes = [AllowAny]

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
