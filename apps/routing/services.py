from typing import Optional, Dict, Any, List
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count
from .models import BankChannel, RoutingRule, RoutingLog


class RoutingService:
    """智能路由服务"""

    @staticmethod
    def list_channels(
        status: Optional[str] = None,
        channel_type: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        queryset = BankChannel.objects.all()
        if status:
            queryset = queryset.filter(status=status)
        if channel_type:
            queryset = queryset.filter(channel_type=channel_type)
        if search:
            queryset = queryset.filter(
                Q(bank_name__icontains=search) | Q(bank_code__icontains=search)
            )
        total = queryset.count()
        paginator = Paginator(queryset.order_by("-priority", "bank_name"), page_size)
        page_obj = paginator.get_page(page)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "results": list(page_obj.object_list.values())
        }

    @staticmethod
    def create_channel(data: Dict[str, Any]) -> BankChannel:
        return BankChannel.objects.create(**data)

    @staticmethod
    def update_channel(channel_id: str, data: Dict[str, Any]) -> Optional[BankChannel]:
        try:
            channel = BankChannel.objects.get(id=channel_id)
            for key, value in data.items():
                if hasattr(channel, key):
                    setattr(channel, key, value)
            channel.save()
            return channel
        except BankChannel.DoesNotExist:
            return None

    @staticmethod
    def delete_channel(channel_id: str) -> bool:
        try:
            BankChannel.objects.get(id=channel_id).delete()
            return True
        except BankChannel.DoesNotExist:
            return False

    @staticmethod
    def get_channel_health(channel_id: str) -> Dict[str, Any]:
        try:
            channel = BankChannel.objects.get(id=channel_id)
            recent_logs = RoutingLog.objects.filter(channel=channel).order_by("-created_at")[:100]
            total = recent_logs.count()
            success = recent_logs.filter(result=RoutingLog.Result.SUCCESS).count()
            avg_time = recent_logs.aggregate(avg=Avg("response_time"))["avg"] or 0
            return {
                "channel_id": str(channel.id),
                "bank_name": channel.bank_name,
                "status": channel.status,
                "total_routes": total,
                "success_count": success,
                "success_rate": round(success / total * 100, 2) if total > 0 else 100.00,
                "avg_response_time": round(avg_time, 2),
                "last_updated": channel.updated_at.isoformat()
            }
        except BankChannel.DoesNotExist:
            return {}

    @staticmethod
    def list_rules(
        status: Optional[str] = None,
        rule_type: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        queryset = RoutingRule.objects.all()
        if status:
            queryset = queryset.filter(status=status)
        if rule_type:
            queryset = queryset.filter(rule_type=rule_type)
        if search:
            queryset = queryset.filter(Q(name__icontains=search))
        total = queryset.count()
        paginator = Paginator(queryset.order_by("-priority", "name"), page_size)
        page_obj = paginator.get_page(page)
        results = []
        for rule in page_obj.object_list:
            results.append({
                "id": str(rule.id),
                "name": rule.name,
                "rule_type": rule.rule_type,
                "status": rule.status,
                "priority": rule.priority,
                "weight": rule.weight,
                "description": rule.description,
                "channel_count": rule.target_channels.count(),
                "created_at": rule.created_at.isoformat()
            })
        return {"total": total, "page": page, "page_size": page_size, "results": results}

    @staticmethod
    def create_rule(data: Dict[str, Any]) -> RoutingRule:
        channel_ids = data.pop("target_channel_ids", [])
        rule = RoutingRule.objects.create(**data)
        if channel_ids:
            rule.target_channels.set(BankChannel.objects.filter(id__in=channel_ids))
        return rule

    @staticmethod
    def update_rule(rule_id: str, data: Dict[str, Any]) -> Optional[RoutingRule]:
        try:
            rule = RoutingRule.objects.get(id=rule_id)
            channel_ids = data.pop("target_channel_ids", None)
            for key, value in data.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)
            rule.save()
            if channel_ids is not None:
                rule.target_channels.set(BankChannel.objects.filter(id__in=channel_ids))
            return rule
        except RoutingRule.DoesNotExist:
            return None

    @staticmethod
    def delete_rule(rule_id: str) -> bool:
        try:
            RoutingRule.objects.get(id=rule_id).delete()
            return True
        except RoutingRule.DoesNotExist:
            return False

    @staticmethod
    def route_select(amount: float, currency: str, country: str) -> Optional[BankChannel]:
        """根据规则选择最优通道"""
        active_channels = BankChannel.objects.filter(status=BankChannel.Status.ACTIVE)
        if not active_channels.exists():
            return None
        # 优先匹配金额规则
        amount_rules = RoutingRule.objects.filter(
            status=RoutingRule.Status.ACTIVE, rule_type=RoutingRule.RuleType.AMOUNT
        ).order_by("priority")
        for rule in amount_rules:
            conditions = rule.conditions or {}
            min_amount = conditions.get("min_amount", 0)
            max_amount = conditions.get("max_amount", float("inf"))
            if min_amount <= amount <= max_amount:
                channels = rule.target_channels.filter(status=BankChannel.Status.ACTIVE)
                if channels.exists():
                    return channels.first()
        # 默认按优先级和成功率选择
        best = active_channels.order_by("-priority", "-success_rate", "avg_response_time").first()
        return best

    @staticmethod
    def list_logs(
        order_no: Optional[str] = None,
        channel_id: Optional[str] = None,
        result: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        queryset = RoutingLog.objects.all()
        if order_no:
            queryset = queryset.filter(order_no__icontains=order_no)
        if channel_id:
            queryset = queryset.filter(channel_id=channel_id)
        if result:
            queryset = queryset.filter(result=result)
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        total = queryset.count()
        paginator = Paginator(queryset.order_by("-created_at"), page_size)
        page_obj = paginator.get_page(page)
        return {
            "total": total, "page": page, "page_size": page_size,
            "results": list(page_obj.object_list.values())
        }
