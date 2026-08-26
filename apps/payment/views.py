"""支付交易 — API Views (运营管理端 + 商户服务端)。"""
from decimal import Decimal, InvalidOperation  # noqa: E402
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.exceptions import BusinessException, ErrorCode
from apps.rbac.permissions import require_permission
from .models import PaymentOrder, RefundOrder, RefundFeeConfig
from .serializers import (
    PaymentOrderSerializer, PaymentOrderListSerializer,
    RefundOrderSerializer, RefundRequestSerializer, RefundReviewSerializer,
    RemittanceApplySerializer,
)
from .services.pre_order import PreOrderService
from .services.payment import PaymentConfirmService
from .services.refund import RefundService
from .services.close_order import CloseOrderService


class PaymentOrderViewSet(viewsets.ReadOnlyModelViewSet):
    """支付订单查询 ViewSet — 运营管理端。"""
    queryset = PaymentOrder.objects.filter(is_deleted=False).select_related("merchant")
    serializer_class = PaymentOrderSerializer
    lookup_field = "order_no"
    lookup_url_kwarg = "order_no"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "pay_method", "merchant__merchant_no", "from_currency", "to_currency"]
    search_fields = ["order_no", "merchant_order_no", "unique_identification_no", "prn_code",
                     "beneficiary_name", "merchant__merchant_name", "merchant__merchant_no"]
    ordering_fields = ["created_at", "amount", "status"]

    def get_serializer_class(self):
        if self.action == "list":
            return PaymentOrderListSerializer
        return PaymentOrderSerializer

    # ── 关单 ──

    @action(detail=True, methods=["post"], url_path="close")
    def close_order(self, request, order_no=None):
        order = self.get_object()
        reason = request.data.get("reason", "")
        service = CloseOrderService()
        service.close_order(order, reason)
        return Response({"message": "Order closed"})

    # ── 统计 ──

    @action(detail=False, methods=["get"], url_path="stats")
    def order_stats(self, request):
        """订单统计 — 仪表盘卡片数据。

        GET /api/v1/admin/orders/stats/
        """
        from django.utils import timezone
        from django.db.models import Sum, Count
        today = timezone.now().date()

        qs = PaymentOrder.objects.filter(is_deleted=False)
        today_qs = qs.filter(created_at__date=today)

        return Response({
            "pending_review": qs.filter(status="PENDING_REVIEW").count(),
            "pending_pay": qs.filter(status="PENDING_PAY").count(),
            "completed_count": qs.filter(status="COMPLETED").count(),
            "today_count": today_qs.count(),
            "today_amount": float(today_qs.aggregate(total=Sum("amount"))["total"] or 0),
            "total_count": qs.count(),
        })

    # ── 资金追踪 ──

    STEP_KEYS = ["created", "review", "collect", "route", "clear", "credit"]

    STATUS_STEP = {
        "PRE_CREATE": "created",
        "PENDING_REVIEW": "review",
        "PROCESSING": "collect",
        "PENDING_PAY": "route",
        "PAY_RECEIVED": "clear",
        "PENDING_SETTLE": "clear",
        "SETTLED": "credit",
        "COMPLETED": "credit",
        "CLOSED": None,
        "REFUNDING": None,
        "REFUNDED": None,
    }

    @action(detail=False, methods=["get"], url_path="trace-fund")
    def trace_fund(self, request):
        """资金追踪 — 查询汇款当前所处阶段与详情。

        支持按平台订单号(RMT...)、商户订单号、PRN、收款人姓名、汇款人姓名检索。
        按汇款人搜索命中多笔时返回 pending_orders 列表；单笔命中返回完整追踪数据。
        """
        order_no = request.query_params.get("order_no", "").strip()
        merchant_order_no = request.query_params.get("merchant_order_no", "").strip()
        prn = request.query_params.get("prn", "").strip()
        beneficiary_name = request.query_params.get("beneficiary_name", "").strip()
        remitter_name = request.query_params.get("remitter_name", "").strip()

        qs = PaymentOrder.objects.filter(is_deleted=False).select_related(
            "merchant"
        ).order_by("-created_at")

        if order_no:
            qs = qs.filter(order_no__icontains=order_no)
        if merchant_order_no:
            qs = qs.filter(merchant_order_no__icontains=merchant_order_no)
        if prn:
            qs = qs.filter(prn_code__icontains=prn)
        if beneficiary_name:
            qs = qs.filter(beneficiary_name__icontains=beneficiary_name)
        if remitter_name:
            qs = qs.filter(merchant__merchant_name__icontains=remitter_name)

        if not qs.exists():
            raise serializers.ValidationError({"detail": "No matching orders found."})

        # If searching by remitter and multiple results, return list
        if remitter_name and qs.count() > 1:
            return Response({
                "pending_orders": [
                    {
                        "order_no": o.order_no,
                        "merchant_order_no": o.merchant_order_no,
                        "beneficiary_name": o.beneficiary_name,
                        "amount": str(o.amount),
                        "from_currency": o.from_currency,
                        "status": o.status,
                        "created_at": o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else "",
                    }
                    for o in qs[:50]
                ]
            })

        order = qs.first()

        # Determine current step
        current_step = self.STATUS_STEP.get(order.status)
        step_idx = (
            self.STEP_KEYS.index(current_step)
            if current_step in self.STEP_KEYS
            else -1
        )

        completed_steps = self.STEP_KEYS[: step_idx + 1] if step_idx >= 0 else []
        all_done = order.status in ("COMPLETED", "REFUNDED")
        terminal = order.status in ("COMPLETED", "CLOSED", "REFUNDED")

        result = {
            "order_no": order.order_no,
            "merchant_order_no": order.merchant_order_no or "",
            "remitter_name": (order.merchant.merchant_name if order.merchant else "") or "",
            "from_currency": order.from_currency,
            "to_currency": order.to_currency,
            "amount": str(order.amount),
            "fee_bearing": order.fee_bearing or "",
            "status": order.status,
            "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S") if order.created_at else "",
            "updated_at": order.updated_at.strftime("%Y-%m-%d %H:%M:%S") if order.updated_at else "",
            "current_step": current_step,
            "step_index": step_idx,
            "completed_steps": completed_steps,
            "all_done": all_done,
            "terminal": terminal,
            "beneficiary_name": order.beneficiary_name or "",
            "beneficiary_account": order.beneficiary_account or "",
            "beneficiary_bank": order.beneficiary_bank or "",
            "beneficiary_swift": order.beneficiary_swift or "",
            "beneficiary_address": order.beneficiary_address or "",
            "prn": order.prn_code or "",
        }

        # Virtual Account (collection VA)
        va = getattr(order, "virtual_account", None)
        if va:
            result["virtual_account"] = {
                "account_no": getattr(va, "account_no", ""),
                "bank_name": getattr(va, "bank_name", ""),
                "balance": str(getattr(va, "balance", 0)),
                "currency": getattr(va, "currency", order.from_currency),
                "is_active": getattr(va, "is_active", True),
            }

        # Nostro / master account
        nostro = getattr(order, "nostro_account", None)
        if nostro:
            result["nostro_account"] = {
                "account_no": getattr(nostro, "account_no", ""),
                "bank_name": getattr(nostro, "bank_name", ""),
                "balance": str(getattr(nostro, "balance", 0)),
                "currency": getattr(nostro, "currency", order.to_currency),
            }

        return Response(result)

    # ── 汇款审核 ──

    @action(detail=True, methods=["post"], url_path="review")
    @require_permission("payment:create")
    def review_remittance(self, request, order_no=None):
        """审核汇款 — approve/reject。

        审核流程：
            PENDING_REVIEW → approve → PENDING_PAY（待付款，此时可申请退款）
            PENDING_REVIEW → reject → CLOSED（需填写驳回原因）
        """
        order = self.get_object()
        action_type = request.data.get("action")
        if action_type not in ("approve", "reject"):
            return Response(
                {"detail": "action must be approve or reject"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if order.status != "PENDING_REVIEW":
            return Response(
                {"detail": f"Current status is {order.status}, can only review orders with PENDING_REVIEW status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone
        now = timezone.now()

        if action_type == "reject":
            reason = request.data.get("reason", "").strip()
            if not reason:
                return Response(
                    {"detail": "Reject reason is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            order.status = "CLOSED"
            order.review_comment = reason
            order.closed_at = now
            order.reviewed_by = request.data.get("reviewed_by", "")
            order.reviewed_at = now
            order.add_status_history("CLOSED", {"reason": reason})
            order.save(update_fields=[
                "status", "reviewed_by", "reviewed_at", "review_comment",
                "closed_at", "updated_at", "status_history",
            ])
            return Response({
                "message": "Remittance rejected",
                "status": order.status,
            })

        # ── approve: PENDING_REVIEW → PENDING_PAY（待付款，此时可申请退款） ──
        order.status = "PENDING_PAY"
        order.prn_code = self._generate_prn_code()
        order.reviewed_by = request.data.get("reviewed_by", "")
        order.reviewed_at = now
        order.review_comment = "Approved"
        order.add_status_history("PENDING_PAY", {
            "reviewed_by": order.reviewed_by,
            "prn_code": order.prn_code,
        })

        order.save(update_fields=[
            "status", "prn_code", "reviewed_by", "reviewed_at", "review_comment",
            "updated_at", "status_history",
        ])

        return Response({
            "message": "Remittance approved, order pending payment",
            "status": order.status,
            "prn_code": order.prn_code,
        })

    def _generate_prn_code(self):
        """生成 PRN 码（使用可配置规则，审核通过时调用）."""
        from apps.payment.models import PRNConfig
        from apps.payment.services.prn_service import generate_prn
        return generate_prn(PRNConfig.get_config())

    # ── 执行汇款（审核+完成，一步到位） ──

    @action(detail=True, methods=["post"], url_path="execute")
    def execute_remittance(self, request, order_no=None):
        """执行汇款 — 审核通过，订单进入待付款状态。

        流程：PENDING_REVIEW → PENDING_PAY（待付款）
        运营人员核对全部信息无误后审核通过。
        """
        # 直接委托 review 逻辑（approve 分支）
        request.data["action"] = "approve"
        request.data["reviewed_by"] = request.data.get("reviewed_by", "")
        return self.review_remittance(request, order_no)

    # ── 确认支付 ──

    @action(detail=True, methods=["post"], url_path="confirm-payment")
    @require_permission("payment:create")
    def confirm_payment(self, request, order_no=None):
        """确认支付 — PENDING_PAY → PAY_RECEIVED，并确保分润记录存在。"""
        order = self.get_object()
        if order.status != "PENDING_PAY":
            return Response(
                {"detail": f"Current status is {order.status}, can only confirm orders with PENDING_PAY status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone
        order.status = "PAY_RECEIVED"
        order.pay_received_at = timezone.now()
        order.bank_txn_id = request.data.get("bank_txn_id", "")
        order.add_status_history("PAY_RECEIVED")
        order.save(update_fields=["status", "pay_received_at", "bank_txn_id", "updated_at", "status_history"])

        # ── 确保分润记录存在（提交时可能因异常而漏建） ──
        fee_share_created = self._ensure_fee_share(order)

        return Response({
            "message": "Payment confirmed",
            "status": order.status,
            "fee_share_created": fee_share_created,
        })

    @staticmethod
    def _ensure_fee_share(order):
        """若订单尚无 FeeShare 记录，自动补建。返回是否新建。"""
        import logging
        logger = logging.getLogger(__name__)
        if order.fee_shares.exists():
            return False
        try:
            from apps.settlement.engine.calculator import SettlementCalculator
            calculator = SettlementCalculator()
            calculator.calculate_fee_share(order)
            logger.info("FeeShare 补建成功 (order=%s)", order.order_no)
            return True
        except Exception as e:
            logger.error("FeeShare 补建失败 (order=%s): %s", order.order_no, e)
            return False

    # ── 汇款申请 ──

    @action(detail=False, methods=["post"], url_path="apply")
    @require_permission("payment:create")
    def apply_remittance(self, request):
        """提交汇款申请。

        提交时强制进行制裁预检。仅当收款人名称**精确/别名**命中 HIGH 风险
        制裁名单时才拦截提交（高置信度），避免操作员跳过前端预检直接提交受
        制裁方汇款；模糊名称/地址/国家等弱信号仅作建议，不自动拦截，以免误伤
        常见姓名或位于制裁国但合法的交易。
        """
        serializer = RemittanceApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        beneficiary_name = serializer.validated_data.get("beneficiary_name", "") or ""
        beneficiary_address = serializer.validated_data.get("beneficiary_address", "") or ""

        from apps.compliance.services import scan_entity_lightweight
        scan = scan_entity_lightweight(beneficiary_name, beneficiary_address)
        for hit in scan.get("name_hits", []):
            if (
                hit.get("risk_level") == "HIGH"
                and hit.get("match_type") in ("exact_name", "alias_name")
            ):
                return Response(
                    {
                        "detail": (
                            "Submission blocked: the beneficiary name exactly matches a "
                            "HIGH-risk sanctioned entity. Please review before proceeding."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        order = serializer.save()
        return Response(PaymentOrderSerializer(order).data, status=status.HTTP_201_CREATED)

    # ── 制裁预检 ──

    @action(detail=False, methods=["post"], url_path="sanction-check")
    def sanction_check(self, request):
        """汇款申请前的制裁预检。

        POST /api/v1/admin/orders/sanction-check/
        Body: {
            "beneficiary_name": "AHMED ALI",
            "beneficiary_address": "123 Main St, Tehran, Iran"
        }

        返回命中结果，包括姓名匹配和地址关键字匹配。
        """
        beneficiary_name = (request.data.get("beneficiary_name") or "").strip()
        beneficiary_address = (request.data.get("beneficiary_address") or "").strip()

        if not beneficiary_name and not beneficiary_address:
            return Response(
                {"detail": "Please provide at least beneficiary name or address"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.compliance.services import scan_entity_lightweight
        result = scan_entity_lightweight(beneficiary_name, beneficiary_address)

        return Response({
            "is_clear": result["is_clear"],
            "name_hits": result["name_hits"],
            "address_hits": result["address_hits"],
            "total_hits": result["total_hits"],
            "warning_message": "" if result["is_clear"] else self._build_warning(result["name_hits"], result["address_hits"]),
        })

    @staticmethod
    def _build_warning(name_hits: list, address_hits: list) -> str:
        """构建制裁警告信息"""
        parts = []
        if name_hits:
            high_names = [h["entity_name"] for h in name_hits if h["risk_level"] == "HIGH"]
            if high_names:
                parts.append("Beneficiary name matches high-risk sanction list: " + ", ".join(high_names[:3]))
            else:
                parts.append("Beneficiary name similar to sanction list: " + ", ".join(h["entity_name"] for h in name_hits[:3]))
            if len(name_hits) > 3:
                parts[-1] += f" ({len(name_hits)} total)"
        if address_hits:
            high_addrs = [h for h in address_hits if h["risk_level"] == "HIGH"]
            if high_addrs:
                parts.append("Beneficiary address matches high-risk sanctioned region: " + ", ".join(h["keyword"] for h in high_addrs[:2]))
            else:
                parts.append("Beneficiary address matches sanction list: " + ", ".join(h["keyword"] for h in address_hits[:2]))
        return "; ".join(parts)

    # ── 确认转账（推入待清算） ──

    @action(detail=True, methods=["post"], url_path="confirm-transfer")
    @require_permission("payment:create")
    def confirm_transfer(self, request, order_no=None):
        """确认已发起银行转账，将订单推入待清算状态。

        PAY_RECEIVED / PENDING_PAY → PENDING_SETTLE

        运营人员确认银行转账已发起后，订单进入待清算队列，
        等待每日结算批次处理。
        """
        order = self.get_object()
        if order.status not in ("PAY_RECEIVED", "PENDING_PAY"):
            return Response(
                {"detail": f"Current status is {order.status}, can only confirm transfer for PAY_RECEIVED or PENDING_PAY orders"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone
        now = timezone.now()

        if order.status == "PENDING_PAY":
            order.pay_received_at = now
        order.status = "PENDING_SETTLE"
        order.bank_txn_id = request.data.get("bank_txn_id", order.bank_txn_id or "")
        order.add_status_history("PENDING_SETTLE", {
            "operator": request.data.get("reviewed_by", ""),
            "bank_txn_id": order.bank_txn_id,
        })
        order.save(update_fields=[
            "status", "bank_txn_id", "pay_received_at", "updated_at", "status_history",
        ])

        return Response({
            "message": "Transfer confirmed, order pending settlement",
            "status": order.status,
            "confirmed_at": now.isoformat(),
        })

    # ── 预订单管理（待清算订单） ──

    @action(detail=False, methods=["get"], url_path="preorders")
    def preorder_list(self, request):
        """查询待清算的汇款预订单。

        GET /api/v1/admin/orders/preorders/
        返回 status=PENDING_SETTLE 的订单，支持筛选、搜索、排序、分页。
        """
        qs = PaymentOrder.objects.filter(
            status="PENDING_SETTLE", is_deleted=False
        ).select_related("merchant").order_by("-created_at")

        # 筛选
        merchant_no = request.query_params.get("merchant_no")
        from_currency = request.query_params.get("from_currency")
        to_currency = request.query_params.get("to_currency")
        search = request.query_params.get("search")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        if merchant_no:
            qs = qs.filter(merchant__merchant_no=merchant_no)
        if from_currency:
            qs = qs.filter(from_currency=from_currency.upper())
        if to_currency:
            qs = qs.filter(to_currency=to_currency.upper())
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(order_no__icontains=search)
                | Q(prn_code__icontains=search)
                | Q(merchant__merchant_name__icontains=search)
                | Q(beneficiary_name__icontains=search)
                | Q(unique_identification_no__icontains=search)
            )
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        # 分页
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = PaymentOrderListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = PaymentOrderListSerializer(qs, many=True)
        return Response({"count": qs.count(), "results": serializer.data})

    # ── 预订单统计 ──

    @action(detail=False, methods=["get"], url_path="preorder-stats")
    def preorder_stats(self, request):
        """预订单统计数据。

        GET /api/v1/admin/orders/preorder-stats/
        """
        from django.db.models import Sum, Count
        from django.utils import timezone

        base_qs = PaymentOrder.objects.filter(status="PENDING_SETTLE", is_deleted=False)
        today = timezone.now().date()
        today_qs = base_qs.filter(updated_at__date=today)

        # 按币种统计
        by_from = base_qs.values("from_currency").annotate(
            count=Count("id"), total=Sum("amount")
        ).order_by("-total")

        by_to = base_qs.values("to_currency").annotate(
            count=Count("id"), total=Sum("settle_amount")
        ).order_by("-total")

        return Response({
            "total_count": base_qs.count(),
            "total_amount": float(base_qs.aggregate(t=Sum("amount"))["t"] or 0),
            "total_settle_amount": float(base_qs.aggregate(t=Sum("settle_amount"))["t"] or 0),
            "total_fee": float(base_qs.aggregate(t=Sum("fee_amount"))["t"] or 0),
            "today_count": today_qs.count(),
            "by_from_currency": [
                {"currency": item["from_currency"], "count": item["count"], "total": float(item["total"])}
                for item in by_from
            ],
            "by_to_currency": [
                {"currency": item["to_currency"], "count": item["count"], "total": float(item["total"])}
                for item in by_to
            ],
        })

    # ── 费用预览 ──

    @action(detail=False, methods=["get"], url_path="fee_preview")
    def fee_preview(self, request):
        """实时预览手续费与结算金额。

        GET /api/v1/admin/orders/fee_preview/?merchant=M20260003&amount=1000&from_currency=USD&to_currency=CNY

        返回：费用明细（手续费率、固定手续费、手续费总额、结算金额、汇率）
        """
        merchant_no = request.query_params.get("merchant")
        amount_str = request.query_params.get("amount")
        from_currency = request.query_params.get("from_currency", "USD")
        to_currency = request.query_params.get("to_currency", "CNY")

        if not merchant_no or not amount_str:
            return Response(
                {"detail": "merchant and amount parameters are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            amount = float(amount_str)
        except (ValueError, TypeError):
            return Response({"detail": "amount must be a valid number"}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({"detail": "Amount must be greater than 0"}, status=status.HTTP_400_BAD_REQUEST)

        # 查询商户
        from apps.merchant.models import Merchant
        try:
            merchant = Merchant.objects.get(merchant_no=merchant_no, is_deleted=False)
        except Merchant.DoesNotExist:
            return Response({"detail": "Merchant not found"}, status=status.HTTP_404_NOT_FOUND)

        # 查询汇率
        from django.utils import timezone
        from apps.exchange.models import ExchangeRate
        today = timezone.now().date()
        try:
            rate_obj = ExchangeRate.objects.get(
                date=today, from_currency=from_currency, to_currency=to_currency, is_deleted=False
            )
            exchange_rate_val = float(rate_obj.rate)
            rate_source = rate_obj.source
        except ExchangeRate.DoesNotExist:
            exchange_rate_val = None
            rate_source = "Not available"

        # 手续费 = 固定手续费 + (汇款金额 × 手续费率)
        fee_rate_pct = float(merchant.fee_rate or 0)
        fixed_fee = float(merchant.fixed_fee or 0)
        percentage_fee = round(amount * fee_rate_pct / 100, 2)
        total_fee = round(percentage_fee + fixed_fee, 2)

        # 到账金额 = 汇款金额 × 汇率 - 手续费（如有汇率）
        if exchange_rate_val:
            target_amount = round(amount * exchange_rate_val, 2)
            settle_amount = round(target_amount - total_fee, 2)
            settle_label = f"{to_currency} {settle_amount:,.2f}"
        else:
            target_amount = amount
            settle_amount = round(amount - total_fee, 2)
            settle_label = f"{settle_amount:,.2f}"

        # 单笔限额 & 日限额
        max_single = float(merchant.max_single_amount) if merchant.max_single_amount else None
        daily_limit_val = float(merchant.daily_limit) if merchant.daily_limit else None

        # 检查今日已用额度
        from django.db.models import Sum
        today_used = PaymentOrder.objects.filter(
            merchant=merchant,
            is_deleted=False,
            created_at__date=today,
        ).exclude(status__in=["CLOSED", "REFUNDED"]).aggregate(
            total=Sum("amount")
        )["total"] or 0
        today_used = float(today_used)
        remaining_daily = round(daily_limit_val - today_used, 2) if daily_limit_val else None

        return Response({
            "merchant_name": merchant.merchant_name,
            "merchant_no": merchant.merchant_no,
            "risk_level": merchant.risk_level,
            "amount": amount,
            "from_currency": from_currency,
            "to_currency": to_currency,
            "exchange_rate": exchange_rate_val,
            "rate_source": rate_source,
            "fee_rate_pct": fee_rate_pct,
            "fixed_fee": fixed_fee,
            "percentage_fee": percentage_fee,
            "total_fee": total_fee,
            "settle_amount": settle_amount,
            "target_amount": target_amount,
            "fee_formula": f"Fixed fee {fixed_fee} + (Amount {amount} x Fee rate {fee_rate_pct}%) = {total_fee}",
            "max_single_amount": max_single,
            "daily_limit": daily_limit_val,
            "today_used": today_used,
            "remaining_daily": remaining_daily,
        })

    @action(detail=True, methods=["post"], url_path="upload-contract")
    @require_permission("payment:create")
    def upload_contract(self, request, order_no=None):
        """上传合同文件，保存到 MEDIA，写入 contract_file 路径。"""
        order = self.get_object()
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "file required"}, status=status.HTTP_400_BAD_REQUEST)
        from django.core.files.storage import default_storage
        from django.conf import settings
        import os
        ext = os.path.splitext(upload.name)[1] or ".bin"
        path = default_storage.save(f"contracts/{order.order_no}{ext}", upload)
        order.contract_file = path
        order.save(update_fields=["contract_file", "updated_at"])
        url = f"{getattr(settings, 'MEDIA_URL', '/media/')}{path}"
        return Response({"contract_file": path, "url": url})

    # ── 退款发起 ──

    @action(detail=True, methods=["post"], url_path="refund-initiate")
    @require_permission("payment:refund")
    def refund_initiate(self, request, order_no=None):
        """对已完成的汇款发起退款。

        资金原路退回客户账户。
        流程：SETTLED / PAY_RECEIVED / PENDING_SETTLE / REFUNDING → 创建 RefundOrder(PENDING_REVIEW)

        POST /api/v1/admin/orders/{order_no}/refund-initiate/
        Body: { "refund_amount": 5000.00, "reason": "客户申请退款" }
        """
        order = self.get_object()

        # ── 可退款状态校验 ──
        REFUNDABLE_STATUSES = ("PENDING_PAY", "SETTLED", "PAY_RECEIVED", "PENDING_SETTLE", "REFUNDING")
        if order.status not in REFUNDABLE_STATUSES:
            return Response(
                {"detail": f"Current status is {order.status}, can only initiate refund for settled orders"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refund_amount = request.data.get("refund_amount")
        reason = request.data.get("reason", "").strip()

        if not refund_amount:
            return Response({"detail": "Refund amount is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not reason:
            return Response({"detail": "Refund reason is required"}, status=status.HTTP_400_BAD_REQUEST)

        from decimal import Decimal, InvalidOperation
        try:
            refund_amount = Decimal(str(refund_amount))
        except (ValueError, TypeError, InvalidOperation):
            return Response({"detail": "Invalid refund amount format"}, status=status.HTTP_400_BAD_REQUEST)

        if refund_amount <= 0:
            return Response({"detail": "Refund amount must be greater than 0"}, status=status.HTTP_400_BAD_REQUEST)
        if refund_amount > order.amount:
            return Response({"detail": f"Refund amount cannot exceed original remittance amount {order.amount}"}, status=status.HTTP_400_BAD_REQUEST)

        # ── 委托 RefundService 处理（含累计金额校验 + 事务原子性） ──
        service = RefundService()
        try:
            refund = service.request_refund(
                payment_order=order,
                refund_amount=refund_amount,
                reason=reason,
            )
        except BusinessException as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": "Refund request submitted, pending review",
            "refund_no": refund.refund_no,
            "refund_amount": str(refund.refund_amount),
            "refund_fee_rate": str(refund.refund_fee_rate),
            "refund_fee_amount": str(refund.refund_fee_amount),
            "status": refund.status,
        }, status=status.HTTP_201_CREATED)


class RefundOrderViewSet(viewsets.ReadOnlyModelViewSet):
    """退款查询 ViewSet — 运营管理端。"""
    queryset = RefundOrder.objects.filter(is_deleted=False).select_related(
        "payment_order", "payment_order__merchant"
    )
    serializer_class = RefundOrderSerializer
    lookup_field = "refund_no"
    lookup_url_kwarg = "refund_no"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status"]
    search_fields = [
        "refund_no",
        "payment_order__order_no",
        "payment_order__prn_code",
        "payment_order__merchant__merchant_name",
    ]
    ordering_fields = ["created_at", "refund_amount"]

    def get_queryset(self):
        qs = super().get_queryset()
        merchant_name = self.request.query_params.get("merchant_name")
        search = self.request.query_params.get("search")
        # search also covers merchant name / PRN (DRF SearchFilter may fail for cross-table Chinese)
        q = merchant_name or search
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(refund_no__icontains=q)
                | Q(payment_order__order_no__icontains=q)
                | Q(payment_order__prn_code__icontains=q)
                | Q(payment_order__merchant__merchant_name__icontains=q)
                | Q(refund_reason__icontains=q)
            ).distinct()
        return qs

    # ── 统计 ──

    @action(detail=False, methods=["get"], url_path="stats")
    def refund_stats(self, request):
        """退款统计 — 仪表盘卡片数据。

        GET /api/v1/admin/refunds/stats/
        """
        from django.utils import timezone
        from django.db.models import Sum
        today = timezone.now().date()

        qs = RefundOrder.objects.filter(is_deleted=False)

        return Response({
            "total_count": qs.count(),
            "pending_review": qs.filter(status="PENDING_REVIEW").count(),
            "processing": qs.filter(status="PROCESSING").count(),
            "success_count": qs.filter(status="SUCCESS").count(),
            "rejected_count": qs.filter(status="REJECTED").count(),
            "today_count": qs.filter(created_at__date=today).count(),
            "today_amount": float(
                qs.filter(created_at__date=today).aggregate(t=Sum("refund_amount"))["t"] or 0
            ),
            "total_amount": float(qs.aggregate(t=Sum("refund_amount"))["t"] or 0),
            "total_fee": float(qs.aggregate(t=Sum("refund_fee_amount"))["t"] or 0),
        })

    # ── 审核 ──

    @action(detail=True, methods=["post"], url_path="review")
    def review(self, request, refund_no=None):
        refund = self.get_object()
        payload = {**request.data}
        # 兼容前端 action=APPROVED / REJECTED
        action = str(payload.get("action", "")).lower()
        if action in ("approved", "approve"):
            payload["action"] = "approve"
        elif action in ("rejected", "reject"):
            payload["action"] = "reject"
        payload.setdefault("reviewer", getattr(request.user, "username", None) or "admin")
        serializer = RefundReviewSerializer(data=payload)
        serializer.is_valid(raise_exception=True)

        service = RefundService()
        data = serializer.validated_data

        if data["action"] == "approve":
            service.approve_refund(refund, data["reviewer"])
            return Response({"message": "Refund approved"})
        else:
            service.reject_refund(refund, data["reviewer"], data.get("reason", ""))
            return Response({"message": "Refund rejected"})

    @action(detail=True, methods=["post"], url_path="execute")
    def execute(self, request, refund_no=None):
        """手动触发已审核通过的退款执行（含失败重试）。"""
        refund = self.get_object()
        if refund.status not in (
            RefundOrder.RefundStatus.APPROVED,
            RefundOrder.RefundStatus.FAILED,
        ):
            return Response(
                {"detail": f"Current status is {refund.status}, only APPROVED/FAILED can execute"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        service = RefundService()
        refund = service.execute_refund(refund)
        return Response(RefundOrderSerializer(refund).data)

    # ── 手续费配置 ──

    @action(detail=False, methods=["get", "put"], url_path="fee-config")
    def fee_config(self, request):
        """获取 / 修改退款手续费率配置。

        GET  /api/v1/admin/refunds/fee-config/
        PUT  /api/v1/admin/refunds/fee-config/  { "fee_rate": 1.50 }
        """
        config = RefundFeeConfig.get_config()
        if request.method == "GET":
            return Response({
                "fee_rate": str(config.fee_rate),
                "updated_at": config.updated_at.isoformat() if config.updated_at else None,
                "updated_by": config.updated_by,
            })
        else:
            fee_rate = request.data.get("fee_rate")
            if fee_rate is None:
                return Response({"detail": "fee_rate is required"}, status=status.HTTP_400_BAD_REQUEST)
            try:
                fee_rate = Decimal(str(fee_rate))
            except (ValueError, InvalidOperation):
                return Response({"detail": "Invalid fee rate format"}, status=status.HTTP_400_BAD_REQUEST)
            if fee_rate < 0 or fee_rate > 100:
                return Response({"detail": "Fee rate must be between 0 and 100"}, status=status.HTTP_400_BAD_REQUEST)

            config.fee_rate = fee_rate
            config.updated_by = request.data.get("updated_by", "admin")
            config.save(update_fields=["fee_rate", "updated_by", "updated_at"])
            return Response({
                "message": "Refund fee rate updated",
                "fee_rate": str(config.fee_rate),
            })


# ── 商户侧视图 ──

class MerchantOrderViewSet(viewsets.ReadOnlyModelViewSet):
    """商户侧订单查询。"""
    serializer_class = PaymentOrderSerializer

    def get_queryset(self):
        # 从认证中获取商户
        merchant = getattr(self.request, "merchant", None)
        merchant_no = self.request.query_params.get("merchant_no")
        if merchant:
            merchant_no = merchant.merchant_no
        if not merchant_no:
            return PaymentOrder.objects.none()
        return PaymentOrder.objects.filter(
            merchant__merchant_no=merchant_no, is_deleted=False
        ).select_related("merchant")


class MerchantRefundViewSet(viewsets.GenericViewSet):
    """商户侧退款。"""
    refund_service = RefundService()

    @action(detail=False, methods=["post"], url_path="apply")
    def apply_refund(self, request):
        """申请退款。"""
        serializer = RefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        try:
            order = PaymentOrder.objects.get(order_no=data["order_no"], is_deleted=False)
        except PaymentOrder.DoesNotExist:
            raise BusinessException(ErrorCode.ORDER_NOT_FOUND)

        refund = self.refund_service.request_refund(
            payment_order=order,
            refund_amount=data["refund_amount"],
            reason=data["reason"],
            idempotency_key=data.get("idempotency_key"),
        )
        return Response(
            RefundOrderSerializer(refund).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="query")
    def query_refunds(self, request):
        """查询退款。"""
        merchant = getattr(request, "merchant", None)
        if not merchant:
            return Response([])

        queryset = RefundOrder.objects.filter(
            payment_order__merchant=merchant, is_deleted=False
        ).select_related("payment_order")

        order_no = request.query_params.get("order_no")
        if order_no:
            queryset = queryset.filter(payment_order__order_no=order_no)

        return Response(RefundOrderSerializer(queryset, many=True).data)
