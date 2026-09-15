from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, List
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count
from apps.core.exceptions import BusinessException
from .models import BankChannel, RoutingRule, RoutingLog

_PAYOUT_BALANCE_FIELDS = {
    "USD": "usd_balance",
    "HKD": "hkd_balance",
    "CNY": "cny_balance",
}


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
                Q(bank_code__icontains=search) | Q(bank_name__icontains=search)
            )
        total = queryset.count()
        paginator = Paginator(queryset.order_by("-priority", "bank_code"), page_size)
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
                "bank_code": channel.bank_code,
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
    def apply_and_log(order, country: str = "CN"):
        """出金/汇款前选择通道并写路由日志。返回选中的 BankChannel（可能为 None）。"""
        from django.conf import settings
        if not getattr(settings, "ENABLE_BANKING", True):
            return None
        channel = None
        try:
            bank_code = getattr(order, "bank_code", None)
            amount = getattr(order, "amount", None)
            if amount is None:
                amount = getattr(order, "settle_net_amount", 0) or 0
            currency = getattr(order, "currency", None) or "CNY"
            if not bank_code:
                channel = RoutingService.route_select(float(amount or 0), currency, country)
                if channel:
                    order.bank_code = channel.bank_code
            else:
                channel = BankChannel.objects.filter(bank_code=bank_code).first()
            RoutingLog.objects.create(
                order_no=getattr(order, "order_no", "") or getattr(order, "batch_no", "") or "",
                channel=channel,
                amount=amount or 0,
                currency=currency,
                result=RoutingLog.Result.SUCCESS if channel else RoutingLog.Result.FAILED,
                request_data={
                    "pay_method": getattr(order, "pay_method", ""),
                    "bank_code": getattr(order, "bank_code", "") or "",
                },
            )
        except Exception:
            pass
        return channel

    @staticmethod
    def route_select(amount: float, currency: str, country: str) -> Optional[BankChannel]:
        """根据规则选择最优通道"""
        from django.conf import settings
        if not getattr(settings, "ENABLE_BANKING", True):
            return None
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
    def payout_amount_for_order(order) -> Decimal:
        sender = getattr(order, "sender_total_amount", None)
        if sender is not None and Decimal(str(sender)) > 0:
            return Decimal(str(sender))
        return Decimal(str(getattr(order, "amount", 0) or 0))

    @staticmethod
    def payout_currency_for_order(order) -> str:
        return (
            getattr(order, "from_currency", None)
            or getattr(order, "currency", None)
            or "USD"
        ).upper()

    @staticmethod
    def _channel_supports_currency(channel: BankChannel, currency: str) -> bool:
        supported = channel.supported_currencies or []
        if not supported:
            return True
        ccy = (currency or "").upper()
        return ccy in {str(item).upper() for item in supported}

    @staticmethod
    def _channel_balance(channel: BankChannel, currency: str) -> Decimal:
        field = _PAYOUT_BALANCE_FIELDS.get((currency or "").upper())
        if not field:
            return Decimal("0")
        return Decimal(str(getattr(channel, field, 0) or 0))

    @staticmethod
    def _channel_fee(channel: BankChannel, amount: Decimal) -> Decimal:
        rate = Decimal(str(channel.fee_rate or 0))
        min_fee = Decimal(str(channel.min_fee or 0))
        max_fee = Decimal(str(channel.max_fee or 0))
        fee = (amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if fee < min_fee:
            fee = min_fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if max_fee > 0 and fee > max_fee:
            fee = max_fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return fee

    @staticmethod
    def rank_payout_banks(amount, currency: str) -> List[Dict[str, Any]]:
        """Rank active channels by computed fee (asc), then bank_code.

        Marks the cheapest bank whose balance covers ``amount`` as recommended.
        """
        payout_amount = Decimal(str(amount or 0))
        ccy = (currency or "").upper()
        rows: List[Dict[str, Any]] = []
        channels = BankChannel.objects.filter(status=BankChannel.Status.ACTIVE)
        for channel in channels:
            if not RoutingService._channel_supports_currency(channel, ccy):
                continue
            fee = RoutingService._channel_fee(channel, payout_amount)
            balance = RoutingService._channel_balance(channel, ccy)
            rows.append({
                "id": str(channel.id),
                "bank_code": channel.bank_code,
                "bank_name": channel.bank_name,
                "fee_rate": str(channel.fee_rate),
                "min_fee": str(channel.min_fee),
                "max_fee": str(channel.max_fee),
                "computed_fee": str(fee),
                "balance": str(balance),
                "currency": ccy,
                "sufficient": balance >= payout_amount,
                "_fee": fee,
            })
        rows.sort(key=lambda row: (row["_fee"], row["bank_code"]))
        recommended_code = next(
            (row["bank_code"] for row in rows if row["sufficient"]),
            None,
        )
        for row in rows:
            row["recommended"] = row["bank_code"] == recommended_code
            row.pop("_fee", None)
        return rows

    @staticmethod
    def select_payout_bank(amount, currency: str, bank_code: str = "") -> Dict[str, Any]:
        ranked = RoutingService.rank_payout_banks(amount, currency)
        requested = (bank_code or "").strip()
        if requested:
            match = next((row for row in ranked if row["bank_code"] == requested), None)
            if not match:
                raise BusinessException(
                    "PAYOUT_BANK_INVALID",
                    "The selected bank is not an active payout channel for this currency",
                    400,
                )
            if not match["sufficient"]:
                raise BusinessException(
                    "PAYOUT_BANK_INSUFFICIENT",
                    "The selected bank does not have sufficient balance for this remittance",
                    400,
                )
            return match
        recommended = next((row for row in ranked if row["recommended"]), None)
        if not recommended:
            raise BusinessException(
                "NO_PAYOUT_BANK",
                "No bank has sufficient balance for this remittance",
                422,
            )
        return recommended

    @staticmethod
    def bind_payout_bank(order, bank_code: str = "") -> Dict[str, Any]:
        """Select a payout bank by fee-then-balance waterfall and persist it on the order."""
        amount = RoutingService.payout_amount_for_order(order)
        currency = RoutingService.payout_currency_for_order(order)
        ranked = RoutingService.rank_payout_banks(amount, currency)
        selected = RoutingService.select_payout_bank(amount, currency, bank_code=bank_code)
        skipped = []
        for row in ranked:
            if row["bank_code"] == selected["bank_code"]:
                break
            skipped.append({
                "bank_code": row["bank_code"],
                "computed_fee": row["computed_fee"],
                "balance": row["balance"],
                "sufficient": row["sufficient"],
            })
        channel = BankChannel.objects.filter(bank_code=selected["bank_code"]).first()
        order.bank_code = selected["bank_code"]
        RoutingLog.objects.create(
            order_no=getattr(order, "order_no", "") or "",
            channel=channel,
            amount=amount or 0,
            currency=currency,
            result=RoutingLog.Result.SUCCESS,
            request_data={
                "pay_method": getattr(order, "pay_method", ""),
                "bank_code": selected["bank_code"],
                "computed_fee": selected["computed_fee"],
                "balance": selected["balance"],
                "skipped_cheaper_banks": skipped,
            },
        )
        return selected

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
