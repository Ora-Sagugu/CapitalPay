from typing import Optional
from decimal import Decimal
from django.db.models import Sum, Count, Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .services import RoutingService
from .serializers import (
    BankChannelSerializer, BankChannelListSerializer, BankChannelCreateUpdateSerializer,
    RoutingRuleSerializer, RoutingLogSerializer, BankTransactionSerializer
)
from .models import BankChannel, RoutingRule, RoutingLog, BankTransaction


class BankChannelViewSet(viewsets.ViewSet):
    """银行通道管理"""
    permission_classes = [AllowAny]

    def list(self, request):
        status_param = request.query_params.get("status")
        channel_type = request.query_params.get("channel_type")
        search = request.query_params.get("search")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        data = RoutingService.list_channels(status_param, channel_type, search, page, page_size)
        return Response(data)

    def create(self, request):
        ser = BankChannelCreateUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        channel = RoutingService.create_channel(ser.validated_data)
        return Response(BankChannelSerializer(channel).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        try:
            channel = BankChannel.objects.get(id=pk)
            return Response(BankChannelSerializer(channel).data)
        except BankChannel.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    def update(self, request, pk=None):
        ser = BankChannelCreateUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        channel = RoutingService.update_channel(pk, ser.validated_data)
        if channel:
            return Response(BankChannelSerializer(channel).data)
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, pk=None):
        if RoutingService.delete_channel(pk):
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["get"])
    def health(self, request, pk=None):
        data = RoutingService.get_channel_health(pk)
        if data:
            return Response(data)
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["get"], url_path="transactions")
    def transactions(self, request, pk=None):
        """获取银行汇款记录。"""
        try:
            channel = BankChannel.objects.get(id=pk)
        except BankChannel.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        txns = BankTransaction.objects.filter(bank=channel).order_by("-txn_date")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        start = (page - 1) * page_size
        end = start + page_size
        serializer = BankTransactionSerializer(txns[start:end], many=True)
        return Response({
            "count": txns.count(),
            "results": serializer.data
        })

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """银行渠道统计概览。"""
        qs = BankChannel.objects.all()
        total = qs.count()
        active = qs.filter(status=BankChannel.Status.ACTIVE).count()
        suspended = qs.filter(status=BankChannel.Status.SUSPENDED).count()
        maintenance = qs.filter(status=BankChannel.Status.MAINTENANCE).count()
        offline = qs.filter(status=BankChannel.Status.OFFLINE).count()

        balances = qs.aggregate(
            total_usd=Sum("usd_balance"),
            total_hkd=Sum("hkd_balance"),
            total_cny=Sum("cny_balance"),
        )

        from django.utils import timezone
        today = timezone.now().date()
        today_txn_count = BankTransaction.objects.filter(
            txn_date__date=today
        ).count()
        total_txn_count = BankTransaction.objects.count()

        return Response({
            "total_channels": total,
            "active": active,
            "suspended": suspended,
            "maintenance": maintenance,
            "offline": offline,
            "total_usd": str(balances["total_usd"] or Decimal("0")),
            "total_hkd": str(balances["total_hkd"] or Decimal("0")),
            "total_cny": str(balances["total_cny"] or Decimal("0")),
            "today_txn_count": today_txn_count,
            "total_txn_count": total_txn_count,
        })

    @action(detail=True, methods=["post"], url_path="toggle-status")
    def toggle_status(self, request, pk=None):
        """切换银行渠道状态 (active ↔ suspended)。"""
        try:
            channel = BankChannel.objects.get(id=pk)
        except BankChannel.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        if channel.status == BankChannel.Status.ACTIVE:
            channel.status = BankChannel.Status.SUSPENDED
        elif channel.status == BankChannel.Status.SUSPENDED:
            channel.status = BankChannel.Status.ACTIVE
        else:
            return Response(
                {"detail": f"当前状态 {channel.status} 不支持快速切换"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        channel.save(update_fields=["status", "updated_at"])
        return Response({
            "message": "状态已切换",
            "status": channel.status,
        })


class RoutingRuleViewSet(viewsets.ViewSet):
    """路由规则管理"""
    permission_classes = [AllowAny]

    def list(self, request):
        status_param = request.query_params.get("status")
        rule_type = request.query_params.get("rule_type")
        search = request.query_params.get("search")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        data = RoutingService.list_rules(status_param, rule_type, search, page, page_size)
        return Response(data)

    def create(self, request):
        ser = RoutingRuleSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        rule = RoutingService.create_rule(ser.validated_data)
        return Response(RoutingRuleSerializer(rule).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        try:
            rule = RoutingRule.objects.get(id=pk)
            return Response(RoutingRuleSerializer(rule).data)
        except RoutingRule.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    def update(self, request, pk=None):
        ser = RoutingRuleSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        rule = RoutingService.update_rule(pk, ser.validated_data)
        if rule:
            return Response(RoutingRuleSerializer(rule).data)
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, pk=None):
        if RoutingService.delete_rule(pk):
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["post"])
    def select(self, request):
        amount = request.data.get("amount", 0)
        currency = request.data.get("currency", "CNY")
        country = request.data.get("country", "CN")
        channel = RoutingService.route_select(float(amount), currency, country)
        if channel:
            return Response({
                "selected_channel": BankChannelSerializer(channel).data,
                "amount": amount,
                "currency": currency,
                "country": country
            })
        return Response({"detail": "No available channel"}, status=status.HTTP_404_NOT_FOUND)


class RoutingLogViewSet(viewsets.ViewSet):
    """路由日志"""
    permission_classes = [AllowAny]

    def list(self, request):
        order_no = request.query_params.get("order_no")
        channel_id = request.query_params.get("channel_id")
        result = request.query_params.get("result")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        data = RoutingService.list_logs(order_no, channel_id, result, start_date, end_date, page, page_size)
        return Response(data)
