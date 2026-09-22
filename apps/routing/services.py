from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, List
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count
from apps.core.exceptions import BusinessException, ErrorCode
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
                Q(bank_code__icontains=search)
                | Q(bank_name__icontains=search)
                | Q(account_number__icontains=search)
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
        channel_ccy = (getattr(channel, "currency", None) or "").upper()
        if not channel_ccy:
            return True
        return channel_ccy == (currency or "").upper()

    @staticmethod
    def _channel_balance(channel: BankChannel, currency: str) -> Decimal:
        if not RoutingService._channel_supports_currency(channel, currency):
            return Decimal("0")
        return Decimal(str(getattr(channel, "balance", 0) or 0))

    @staticmethod
    def _channel_fee(channel: BankChannel, amount: Decimal) -> Decimal:
        rate = Decimal(str(channel.fee_rate or 0))
        max_fee = Decimal(str(channel.max_fee or 0))
        fee = (amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if max_fee > 0 and fee > max_fee:
            fee = max_fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return fee

    @staticmethod
    def _money(value) -> Decimal:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _remittance_fee(remittance_fee) -> Optional[Decimal]:
        if remittance_fee is None or remittance_fee == "":
            return None
        return RoutingService._money(remittance_fee)

    @staticmethod
    def _payout_channels(currency: str) -> List[BankChannel]:
        ccy = (currency or "").upper()
        channels = []
        for channel in BankChannel.objects.filter(status=BankChannel.Status.ACTIVE):
            if RoutingService._channel_supports_currency(channel, ccy):
                channels.append(channel)
        return channels

    @staticmethod
    def normalize_payout_bank_codes(bank_code: str = "", bank_codes=None) -> List[str]:
        codes: List[str] = []
        if bank_codes:
            if isinstance(bank_codes, str):
                raw = [part.strip() for part in bank_codes.split(",")]
            else:
                raw = list(bank_codes)
            for item in raw:
                code = str(item or "").strip()
                if code and code not in codes:
                    codes.append(code)
        requested = (bank_code or "").strip()
        if requested and requested not in codes:
            codes.insert(0, requested)
        return codes

    @staticmethod
    def _split_leg(row: Dict[str, Any], amount: Decimal, fee: Decimal) -> Dict[str, Any]:
        return {
            "bank_code": row["bank_code"],
            "bank_name": row["bank_name"],
            "amount": str(RoutingService._money(amount)),
            "computed_fee": str(RoutingService._money(fee)),
            "balance": row["balance"],
            "currency": row.get("currency", ""),
        }

    @staticmethod
    def _build_split_plan(
        first: Dict[str, Any],
        second: Dict[str, Any],
        payout_amount: Decimal,
        remittance: Optional[Decimal],
        channels_by_code: Dict[str, BankChannel],
    ) -> Optional[Dict[str, Any]]:
        first_balance = RoutingService._money(first["balance"])
        if first_balance <= 0 or first_balance >= payout_amount:
            return None
        remainder = RoutingService._money(payout_amount - first_balance)
        if remainder <= 0:
            return None
        second_balance = RoutingService._money(second["balance"])
        if second_balance < remainder:
            return None
        first_channel = channels_by_code.get(first["bank_code"])
        second_channel = channels_by_code.get(second["bank_code"])
        if first_channel is None or second_channel is None:
            return None
        first_fee = RoutingService._channel_fee(first_channel, first_balance)
        second_fee = RoutingService._channel_fee(second_channel, remainder)
        total_fee = RoutingService._money(first_fee + second_fee)
        if remittance is not None and total_fee >= remittance:
            return None
        splits = [
            RoutingService._split_leg(first, first_balance, first_fee),
            RoutingService._split_leg(second, remainder, second_fee),
        ]
        return {
            "bank_code": first["bank_code"],
            "computed_fee": str(total_fee),
            "splits": splits,
            "recommended": False,
        }

    @staticmethod
    def _single_bank_plan(row: Dict[str, Any], payout_amount: Decimal) -> Dict[str, Any]:
        fee = RoutingService._money(row["computed_fee"])
        return {
            "bank_code": row["bank_code"],
            "computed_fee": str(fee),
            "splits": [RoutingService._split_leg(row, payout_amount, fee)],
            "recommended": bool(row.get("recommended")),
        }

    @staticmethod
    def _recommended_plan(
        rows: List[Dict[str, Any]],
        payout_amount: Decimal,
        remittance: Optional[Decimal],
        channels_by_code: Dict[str, BankChannel],
    ) -> Optional[Dict[str, Any]]:
        for row in rows:
            balance = RoutingService._money(row["balance"])
            if balance <= 0:
                continue
            if row["sufficient"] and row["bank_fee_ok"]:
                plan = RoutingService._single_bank_plan(row, payout_amount)
                plan["recommended"] = True
                return plan
            if not row["partial"]:
                continue
            for partner in rows:
                if partner["bank_code"] == row["bank_code"]:
                    continue
                plan = RoutingService._build_split_plan(
                    row, partner, payout_amount, remittance, channels_by_code,
                )
                if plan:
                    plan["recommended"] = True
                    return plan
        return None

    @staticmethod
    def rank_payout_banks(amount, currency: str, remittance_fee=None) -> List[Dict[str, Any]]:
        """Rank active channels by Bank Fee (asc), then bank_code.

        Marks the cheapest viable plan as recommended: a leftover split when the
        cheapest bank cannot cover the payout, otherwise the first bank that both
        covers ``amount`` and whose Bank Fee is strictly less than ``remittance_fee``.
        """
        payout_amount = RoutingService._money(amount)
        ccy = (currency or "").upper()
        remittance = RoutingService._remittance_fee(remittance_fee)
        rows: List[Dict[str, Any]] = []
        channels_by_code: Dict[str, BankChannel] = {}
        for channel in RoutingService._payout_channels(ccy):
            fee = RoutingService._channel_fee(channel, payout_amount)
            balance = RoutingService._channel_balance(channel, ccy)
            balance_ok = balance >= payout_amount
            bank_fee_ok = remittance is None or fee < remittance
            usable = min(balance, payout_amount) if balance > 0 else Decimal("0.00")
            channels_by_code[channel.bank_code] = channel
            rows.append({
                "id": str(channel.id),
                "bank_code": channel.bank_code,
                "bank_name": channel.bank_name,
                "fee_rate": str(channel.fee_rate),
                "max_fee": str(channel.max_fee),
                "computed_fee": str(fee),
                "balance": str(balance),
                "usable_amount": str(RoutingService._money(usable)),
                "currency": ccy,
                "sufficient": balance_ok,
                "partial": balance > 0 and not balance_ok,
                "bank_fee_ok": bank_fee_ok,
                "selectable": False,
                "_fee": fee,
            })
        rows.sort(key=lambda row: (row["_fee"], row["bank_code"]))
        recommended = RoutingService._recommended_plan(
            rows, payout_amount, remittance, channels_by_code,
        )
        recommended_codes = {
            leg["bank_code"] for leg in (recommended or {}).get("splits") or []
        }
        for row in rows:
            if row["sufficient"] and row["bank_fee_ok"]:
                row["selectable"] = True
            elif row["partial"]:
                row["selectable"] = any(
                    RoutingService._build_split_plan(
                        row, partner, payout_amount, remittance, channels_by_code,
                    )
                    for partner in rows
                    if partner["bank_code"] != row["bank_code"]
                )
            row["recommended"] = row["bank_code"] in recommended_codes
            row.pop("_fee", None)
        return rows

    @staticmethod
    def payout_plan_from_ranked(
        ranked: List[Dict[str, Any]],
        amount,
        currency: str,
        remittance_fee=None,
    ) -> Optional[Dict[str, Any]]:
        payout_amount = RoutingService._money(amount)
        remittance = RoutingService._remittance_fee(remittance_fee)
        channels_by_code = {
            channel.bank_code: channel
            for channel in RoutingService._payout_channels(currency)
        }
        return RoutingService._recommended_plan(
            ranked, payout_amount, remittance, channels_by_code,
        )

    @staticmethod
    def select_payout_plan(
        amount,
        currency: str,
        bank_code: str = "",
        bank_codes=None,
        remittance_fee=None,
    ) -> Dict[str, Any]:
        payout_amount = RoutingService._money(amount)
        remittance = RoutingService._remittance_fee(remittance_fee)
        ranked = RoutingService.rank_payout_banks(
            amount, currency, remittance_fee=remittance_fee,
        )
        channels_by_code = {
            channel.bank_code: channel
            for channel in RoutingService._payout_channels(currency)
        }
        requested = RoutingService.normalize_payout_bank_codes(bank_code, bank_codes)
        if not requested:
            recommended = RoutingService._recommended_plan(
                ranked, payout_amount, remittance, channels_by_code,
            )
            if not recommended:
                raise BusinessException(
                    ErrorCode.NO_PAYOUT_BANK,
                    "No bank has sufficient balance and a Bank Fee below Remittance Fee",
                    422,
                )
            return recommended

        if len(requested) > 2:
            raise BusinessException(
                ErrorCode.PAYOUT_BANK_SPLIT_INVALID,
                "A payout can use at most two banks",
                400,
            )

        matches = []
        for code in requested:
            match = next((row for row in ranked if row["bank_code"] == code), None)
            if not match:
                raise BusinessException(
                    ErrorCode.PAYOUT_BANK_INVALID,
                    "The selected bank is not an active payout channel for this currency",
                    400,
                )
            matches.append(match)

        if len(matches) == 1:
            match = matches[0]
            if not match["sufficient"]:
                raise BusinessException(
                    ErrorCode.PAYOUT_BANK_INSUFFICIENT,
                    "The selected bank does not have sufficient balance for this remittance",
                    400,
                )
            if not match["bank_fee_ok"]:
                raise BusinessException(
                    ErrorCode.PAYOUT_BANK_FEE_EXCEEDS,
                    "Bank Fee must be less than Remittance Fee",
                    400,
                )
            return RoutingService._single_bank_plan(match, payout_amount)

        leftover = [
            row for row in matches
            if RoutingService._money(row["balance"]) > 0
            and RoutingService._money(row["balance"]) < payout_amount
        ]
        covering = [row for row in matches if row not in leftover]
        if len(leftover) == 0:
            raise BusinessException(
                ErrorCode.PAYOUT_BANK_SPLIT_INVALID,
                "A second bank can only be used when the first bank's remaining balance cannot cover the payout",
                400,
            )
        if len(leftover) == 2:
            leftover.sort(key=lambda row: (RoutingService._money(row["computed_fee"]), row["bank_code"]))
            first, second = leftover[0], leftover[1]
        else:
            first = leftover[0]
            second = covering[0] if covering else leftover[1]
        plan = RoutingService._build_split_plan(
            first, second, payout_amount, remittance, channels_by_code,
        )
        if not plan:
            second_balance = RoutingService._money(second["balance"])
            remainder = RoutingService._money(
                payout_amount - RoutingService._money(first["balance"]),
            )
            if second_balance < remainder:
                raise BusinessException(
                    ErrorCode.PAYOUT_BANK_INSUFFICIENT,
                    "The selected banks do not have sufficient combined balance for this remittance",
                    400,
                )
            raise BusinessException(
                ErrorCode.PAYOUT_BANK_FEE_EXCEEDS,
                "Bank Fee must be less than Remittance Fee",
                400,
            )
        return plan

    @staticmethod
    def select_payout_bank(
        amount, currency: str, bank_code: str = "", remittance_fee=None, bank_codes=None,
    ) -> Dict[str, Any]:
        plan = RoutingService.select_payout_plan(
            amount,
            currency,
            bank_code=bank_code,
            bank_codes=bank_codes,
            remittance_fee=remittance_fee,
        )
        primary_code = plan["bank_code"]
        ranked = RoutingService.rank_payout_banks(
            amount, currency, remittance_fee=remittance_fee,
        )
        match = next((row for row in ranked if row["bank_code"] == primary_code), None)
        selected = dict(match or {"bank_code": primary_code})
        selected["computed_fee"] = plan["computed_fee"]
        selected["splits"] = plan["splits"]
        selected["recommended"] = bool(plan.get("recommended"))
        return selected

    @staticmethod
    def bind_payout_bank(order, bank_code: str = "", bank_codes=None) -> Dict[str, Any]:
        """Select payout bank(s) by fee-then-balance waterfall and persist them."""
        amount = RoutingService.payout_amount_for_order(order)
        currency = RoutingService.payout_currency_for_order(order)
        remittance_fee = getattr(order, "fee_amount", None)
        ranked = RoutingService.rank_payout_banks(
            amount, currency, remittance_fee=remittance_fee,
        )
        selected = RoutingService.select_payout_bank(
            amount,
            currency,
            bank_code=bank_code,
            bank_codes=bank_codes,
            remittance_fee=remittance_fee,
        )
        skipped = []
        bound_codes = {leg["bank_code"] for leg in selected.get("splits") or []}
        for row in ranked:
            if row["bank_code"] in bound_codes:
                break
            skipped.append({
                "bank_code": row["bank_code"],
                "computed_fee": row["computed_fee"],
                "balance": row["balance"],
                "sufficient": row["sufficient"],
                "bank_fee_ok": row["bank_fee_ok"],
                "selectable": row["selectable"],
            })
        channel = BankChannel.objects.filter(bank_code=selected["bank_code"]).first()
        order.bank_code = selected["bank_code"]
        order.payout_splits = selected.get("splits") or []
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
                "remittance_fee": str(remittance_fee or 0),
                "balance": selected.get("balance"),
                "splits": selected.get("splits") or [],
                "skipped_cheaper_banks": skipped,
            },
        )
        return selected

    @staticmethod
    def channel_fee_for_order(order, payout_amount: Optional[Decimal] = None) -> Decimal:
        """Bank Fee for an order, summing split legs when two banks were used."""
        amount = payout_amount
        if amount is None:
            amount = RoutingService.payout_amount_for_order(order)
        splits = [leg for leg in (getattr(order, "payout_splits", None) or []) if leg]
        if len(splits) >= 2:
            total = Decimal("0.00")
            for leg in splits:
                channel = BankChannel.objects.filter(bank_code=leg.get("bank_code")).first()
                if channel is None:
                    continue
                total += RoutingService._channel_fee(
                    channel, RoutingService._money(leg.get("amount")),
                )
            return RoutingService._money(total)
        bank_code = getattr(order, "bank_code", "") or ""
        if not bank_code:
            return Decimal("0.00")
        channel = BankChannel.objects.filter(bank_code=bank_code).first()
        if channel is None:
            return Decimal("0.00")
        return RoutingService._channel_fee(channel, Decimal(str(amount or 0)))

    @staticmethod
    def payout_bank_names_for_order(order) -> str:
        splits = [leg for leg in (getattr(order, "payout_splits", None) or []) if leg]
        names = []
        for leg in splits:
            name = (leg.get("bank_name") or "").strip()
            code = (leg.get("bank_code") or "").strip()
            if name:
                names.append(name)
            elif code:
                channel = BankChannel.objects.filter(bank_code=code).first()
                names.append(channel.bank_name if channel else code)
        if names:
            return " + ".join(names)
        bank_code = getattr(order, "bank_code", "") or ""
        if not bank_code:
            return ""
        channel = BankChannel.objects.filter(bank_code=bank_code).first()
        return channel.bank_name if channel else bank_code

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
