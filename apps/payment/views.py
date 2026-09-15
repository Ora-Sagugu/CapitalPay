"""支付交易 — API Views (运营管理端 + 商户服务端)。"""
from decimal import Decimal, InvalidOperation  # noqa: E402
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction

from apps.core.exceptions import BusinessException, ErrorCode
from apps.rbac.permissions import RequiresFeature
from apps.openapi.authentication import HMACAuthentication, HasHMACPrincipal
from apps.rbac.authentication import JWTAuthentication
from .models import PaymentOrder, RefundOrder, RefundFeeConfig
from .serializers import (
    PaymentOrderSerializer, PaymentOrderListSerializer, PaymentOrderDetailSerializer,
    RefundOrderSerializer, RefundRequestSerializer, RefundReviewSerializer,
    RemittanceQuoteRequestSerializer, RemittanceSubmitSerializer,
)
from .services.pre_order import PreOrderService
from .services.payment import PaymentConfirmService
from .services.refund import RefundService
from .services.close_order import CloseOrderService
from .services.remittance_application import RemittanceApplicationService
from .services.remittance_quote import RemittanceQuoteService


class PaymentOrderViewSet(RequiresFeature, viewsets.ReadOnlyModelViewSet):
    """支付订单查询 ViewSet — 运营管理端。"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    feature_code = "feature:orders"
    ACTION_FEATURES = {
        "trace_fund": "feature:fund_trace",
        "preorder_list": "feature:pre_orders",
        "preorder_stats": "feature:pre_orders",
        "review_remittance": "feature:orders.approve",
        "execute_remittance": "feature:orders.approve",
        "confirm_transfer": "feature:orders.approve",
        "confirm_payment": "feature:orders.approve",
        "payout_banks": "feature:orders.approve",
        "close_order": "feature:orders.approve",
        "manual_confirm": "feature:orders.approve",
        "refund_initiate": "feature:orders.approve",
    }
    queryset = PaymentOrder.objects.filter(is_deleted=False).select_related("merchant")
    serializer_class = PaymentOrderSerializer
    lookup_field = "order_no"
    lookup_url_kwarg = "order_no"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "pay_method", "merchant__merchant_no", "from_currency", "to_currency"]
    search_fields = ["order_no", "merchant_order_no", "unique_identification_no", "prn_code",
                     "beneficiary_name", "merchant__merchant_name", "merchant__merchant_no"]
    ordering_fields = ["created_at", "amount", "status"]

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, "action", None) == "retrieve":
            return qs.select_related("merchant", "quote").prefetch_related("refunds")
        if getattr(self, "action", None) == "sanction_review":
            return qs.select_related("merchant")
        if getattr(self, "action", None) == "list":
            status_filter = (self.request.query_params.get("status") or "").strip()
            if status_filter != PaymentOrder.OrderStatus.PENDING_AGENT_REVIEW:
                qs = qs.exclude(status=PaymentOrder.OrderStatus.PENDING_AGENT_REVIEW)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return PaymentOrderListSerializer
        if self.action == "retrieve":
            return PaymentOrderDetailSerializer
        return PaymentOrderSerializer

    # ── 关单 ──

    @action(detail=True, methods=["post"], url_path="close")
    def close_order(self, request, order_no=None):
        order = self.get_object()
        reason = request.data.get("reason", "")
        service = CloseOrderService()
        service.close_order(order, reason)
        return Response({"message": "Order closed"})

    @action(detail=True, methods=["post"], url_path="notify-retry")
    def notify_retry(self, request, order_no=None):
        order = self.get_object()
        from apps.payment.services.notify import trigger_order_notify
        trigger_order_notify(order)
        order.refresh_from_db()
        return Response({"message": "Notification triggered", "notify_status": order.notify_status})

    @action(detail=True, methods=["post"], url_path="manual-confirm")
    def manual_confirm(self, request, order_no=None):
        order = self.get_object()
        service = PaymentConfirmService()
        service.manual_confirm(str(order.id), bank_txn_id=request.data.get("bank_txn_id"))
        order.refresh_from_db()
        return Response({"message": "Collection has been confirmed", "status": order.status})

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
            "pending_pay": qs.filter(status__in=["PENDING_PAY", "PRE_CREATE", "PROCESSING"]).count(),
            "completed_count": qs.filter(status__in=["SETTLED", "COMPLETED"]).count(),
            "today_count": today_qs.count(),
            "today_amount": float(today_qs.aggregate(total=Sum("amount"))["total"] or 0),
            "total_count": qs.count(),
        })

    # ── 资金追踪 ──

    @action(detail=False, methods=["get"], url_path="trace-fund")
    def trace_fund(self, request):
        """资金追踪 — 查询汇款资金去向与收款 VA。

        统一参数 q：平台订单号 / 商户订单号 / PRN / 收款人 / 汇款人（商户名），OR 检索。
        兼容旧字段 order_no、merchant_order_no、prn、beneficiary_name、remitter_name。
        selected_order_no 指定展开哪一笔；缺省为命中集中最新一条。
        """
        from apps.payment.services.fund_trace import FundTraceNotFound, trace_fund

        try:
            result = trace_fund(
                q=request.query_params.get("q", ""),
                order_no=request.query_params.get("order_no", ""),
                merchant_order_no=request.query_params.get("merchant_order_no", ""),
                prn=request.query_params.get("prn", ""),
                beneficiary_name=request.query_params.get("beneficiary_name", ""),
                remitter_name=request.query_params.get("remitter_name", ""),
                selected_order_no=request.query_params.get("selected_order_no", ""),
            )
        except FundTraceNotFound as exc:
            raise serializers.ValidationError({"detail": str(exc)})
        return Response(result)

    # ── 汇款审核 ──

    @action(detail=True, methods=["post"], url_path="review")
    @transaction.atomic
    def review_remittance(self, request, order_no=None):
        """审核汇款 — approve/reject。

        审核流程：
            PENDING_REVIEW → approve → PENDING_PAY（待付款，此时可申请退款）
            PENDING_REVIEW → reject → CLOSED（需填写驳回原因）
        """
        order = PaymentOrder.objects.select_for_update().select_related(
            "merchant", "merchant__agent"
        ).get(pk=self.get_object().pk)
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
            order.reviewed_by = getattr(request.user, "username", "") or str(request.user.pk)
            order.reviewed_at = now
            order.add_status_history("CLOSED", {"reason": reason})
            order.save(update_fields=[
                "status", "reviewed_by", "reviewed_at", "review_comment",
                "closed_at", "updated_at", "status_history",
            ])
            RemittanceApplicationService().release_reserved_usage(order)
            return Response({
                "message": "Remittance rejected",
                "status": order.status,
            })

        # ── approve: PENDING_REVIEW → PENDING_PAY（待付款，此时可申请退款） ──
        from apps.payment.services.remittance_policy import RemittanceEligibilityPolicy
        RemittanceEligibilityPolicy().assert_eligible(
            order.merchant, order.amount, include_usage=False
        )
        order.status = "PENDING_PAY"
        from apps.payment.services.prn_service import bind_prn_to_order
        requested = (request.data.get("prn_code") or order.prn_code or "").strip()
        order.prn_code = bind_prn_to_order(order, requested)
        order.reviewed_by = getattr(request.user, "username", "") or str(request.user.pk)
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

    def _generate_prn_code(self, order=None):
        """生成 PRN 码（审核通过时调用）."""
        from apps.payment.services.prn_service import generate_prn
        return generate_prn(order=order)

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
    def confirm_payment(self, request, order_no=None):
        """确认支付 — PENDING_PAY → PAY_RECEIVED，并确保分润记录存在。"""
        order = self.get_object()
        if order.status != "PENDING_PAY":
            return Response(
                {"detail": f"Current status is {order.status}, can only confirm orders with PENDING_PAY status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.payment.services.payment import PaymentConfirmService
        confirmed = PaymentConfirmService().manual_confirm_by_order_no(
            order.order_no,
            bank_txn_id=request.data.get("bank_txn_id", "") or "",
        )
        fee_share_created = self._ensure_fee_share(confirmed)
        return Response({
            "message": "Payment confirmed",
            "status": confirmed.status,
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
    def apply_remittance(self, request):
        """使用有效报价原子提交汇款申请。"""
        serializer = RemittanceSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from .models import RemittanceQuote
        quote = RemittanceQuote.objects.filter(
            quote_no=serializer.validated_data["quote_id"], is_deleted=False
        ).select_related("merchant").first()
        if not quote:
            raise BusinessException("QUOTE_NOT_FOUND", "The quotation does not exist; please obtain a new quotation", 404)
        order, created = RemittanceApplicationService().submit(
            merchant=quote.merchant,
            payload=serializer.validated_data,
            idempotency_key=request.headers.get("Idempotency-Key", ""),
            actor_type="ADMIN",
        )
        return Response(
            PaymentOrderSerializer(order).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

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
        blocked = any(
            hit.get("risk_level") == "HIGH"
            and hit.get("match_type") in ("exact_name", "alias_name")
            for hit in result["name_hits"]
        )

        return Response({
            "is_clear": result["is_clear"],
            "blocked": blocked,
            "name_hits": result["name_hits"],
            "address_hits": result["address_hits"],
            "country_hits": result.get("country_hits", []),
            "total_hits": result["total_hits"],
            "warning_message": "" if result["is_clear"] else self._build_warning(
                result["name_hits"], result["address_hits"], result.get("country_hits", [])
            ),
        })

    @action(detail=True, methods=["get"], url_path="sanction-review")
    def sanction_review(self, request, order_no=None):
        """只读：按订单收款人信息比对当前制裁名单，不写扫描记录。

        GET /api/v1/admin/orders/{order_no}/sanction-review/
        """
        order = self.get_object()
        from apps.compliance.services import scan_entity_lightweight

        result = scan_entity_lightweight(
            order.beneficiary_name or "",
            order.beneficiary_address or "",
        )
        blocked = any(
            hit.get("risk_level") == "HIGH"
            and hit.get("match_type") in ("exact_name", "alias_name")
            for hit in result["name_hits"]
        )
        merchant = getattr(order, "merchant", None)
        return Response({
            "order_no": order.order_no,
            "is_clear": result["is_clear"],
            "blocked": blocked,
            "total_hits": result["total_hits"],
            "warning_message": "" if result["is_clear"] else self._build_warning(
                result["name_hits"], result["address_hits"], result.get("country_hits", [])
            ),
            "screened": {
                "beneficiary_name": order.beneficiary_name or "",
                "beneficiary_address": order.beneficiary_address or "",
                "customer_name": merchant.merchant_name if merchant else "",
                "customer_sanction_status": getattr(merchant, "sanction_status", "") or "",
            },
            "name_hits": result["name_hits"],
            "address_hits": result["address_hits"],
            "country_hits": result.get("country_hits", []),
        })

    @staticmethod
    def _build_warning(name_hits: list, address_hits: list, country_hits: list | None = None) -> str:
        from apps.compliance.services import build_sanction_warning
        return build_sanction_warning(name_hits, address_hits, country_hits)

    @action(detail=True, methods=["get"], url_path="payout-banks")
    def payout_banks(self, request, order_no=None):
        """Rank payout banks by Fee Rule then Balances for this instruction."""
        from apps.routing.services import RoutingService

        order = self.get_object()
        amount = RoutingService.payout_amount_for_order(order)
        currency = RoutingService.payout_currency_for_order(order)
        ranked = RoutingService.rank_payout_banks(amount, currency)
        recommended = next((row for row in ranked if row["recommended"]), None)
        return Response({
            "order_no": order.order_no,
            "amount": str(amount),
            "currency": currency,
            "recommended_bank_code": recommended["bank_code"] if recommended else None,
            "results": ranked,
        })

    # ── 确认转账（推入待清算） ──

    @action(detail=True, methods=["post"], url_path="confirm-transfer")
    def confirm_transfer(self, request, order_no=None):
        """确认已发起银行转账，将订单推入待清算状态。

        PAY_RECEIVED / PENDING_PAY → PENDING_SETTLE

        运营人员确认银行转账已发起后，订单进入待清算队列，
        等待每日结算批次处理。汇出银行按 Fee Rule 升序、余额是否足够瀑布选择。
        """
        order = self.get_object()
        if order.status not in ("PAY_RECEIVED", "PENDING_PAY"):
            return Response(
                {"detail": f"Current status is {order.status}, can only confirm transfer for PAY_RECEIVED or PENDING_PAY orders"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone
        from apps.payment.services.payment import PaymentConfirmService
        from apps.payment.services.remittance_application import assert_confirm_transfer_allowed
        from apps.routing.services import RoutingService

        assert_confirm_transfer_allowed(order)

        now = timezone.now()
        selected = RoutingService.bind_payout_bank(
            order, bank_code=(request.data.get("bank_code") or "").strip(),
        )
        order.save(update_fields=["bank_code", "updated_at"])

        if order.status == "PENDING_PAY":
            order = PaymentConfirmService().manual_confirm_by_order_no(
                order.order_no,
                bank_txn_id=request.data.get("bank_txn_id", "") or order.bank_txn_id or "",
            )
            self._ensure_fee_share(order)

        order.refresh_from_db()
        if order.status == "PAY_RECEIVED":
            from apps.account.services import AccountService
            AccountService().debit_va_for_order_outflow(
                order,
                remark=f"Confirm transfer {order.order_no}",
            )
            order.status = "PENDING_SETTLE"
            if request.data.get("bank_txn_id"):
                order.bank_txn_id = request.data.get("bank_txn_id")
            order.add_status_history("PENDING_SETTLE", {
                "operator": request.data.get("reviewed_by", ""),
                "bank_txn_id": order.bank_txn_id,
                "bank_code": order.bank_code,
            })
            order.save(update_fields=[
                "status", "bank_txn_id", "bank_code", "pay_received_at",
                "updated_at", "status_history",
            ])
            from apps.payment.services.notify import trigger_order_notify
            trigger_order_notify(order)

        return Response({
            "message": "Transfer confirmed, order pending settlement",
            "status": order.status,
            "bank_code": order.bank_code,
            "computed_fee": selected.get("computed_fee"),
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

    # ── 汇款报价 ──

    def _create_remittance_quote(self, data):
        serializer = RemittanceQuoteRequestSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        merchant_no = serializer.validated_data.get("merchant", "")
        if not merchant_no:
            raise BusinessException("MERCHANT_REQUIRED", "Please select the remitting customer", 400)
        from apps.merchant.models import Merchant
        merchant = Merchant.objects.filter(
            merchant_no=merchant_no, is_deleted=False
        ).select_related("agent").first()
        if not merchant:
            raise BusinessException("MERCHANT_NOT_FOUND", "The customer does not exist or has been closed", 404)
        quote = RemittanceQuoteService().create_quote(
            merchant=merchant,
            amount=serializer.validated_data["amount"],
            from_currency=serializer.validated_data["from_currency"],
            to_currency=serializer.validated_data["to_currency"],
            fee_bearing=serializer.validated_data["fee_bearing"],
            actor_type="ADMIN",
        )
        return RemittanceQuoteService.serialize(quote)

    @action(detail=False, methods=["post"], url_path="quote")
    def quote_remittance(self, request):
        return Response(
            self._create_remittance_quote(request.data),
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="fee_preview")
    def fee_preview(self, request):
        """兼容旧客户端；返回与 POST quote 相同的可提交报价。"""
        return Response(self._create_remittance_quote(request.query_params))

    @action(detail=True, methods=["post"], url_path="upload-contract")
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
    def refund_initiate(self, request, order_no=None):
        """对已完成的汇款发起退款。

        资金原路退回客户账户。
        流程：SETTLED / PAY_RECEIVED / PENDING_SETTLE / REFUNDING → 创建 RefundOrder(PENDING_REVIEW)

        POST /api/v1/admin/orders/{order_no}/refund-initiate/
        Body: { "refund_amount": 5000.00, "reason": "客户申请退款" }
        """
        order = self.get_object()

        # ── 可退款状态校验 ──
        REFUNDABLE_STATUSES = ("PENDING_PAY", "SETTLED", "COMPLETED", "PAY_RECEIVED", "PENDING_SETTLE", "REFUNDING")
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


class RefundOrderViewSet(RequiresFeature, viewsets.ReadOnlyModelViewSet):
    """退款查询 ViewSet — 运营管理端。"""
    authentication_classes = [JWTAuthentication]
    feature_code = "feature:refunds"
    ACTION_FEATURES = {
        "review": "feature:refunds.approve",
        "execute": "feature:refunds.approve",
    }
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
    authentication_classes = [HMACAuthentication]
    permission_classes = [HasHMACPrincipal]
    serializer_class = PaymentOrderSerializer

    def get_queryset(self):
        merchant = getattr(self.request, "merchant", None)
        if not merchant:
            return PaymentOrder.objects.none()
        qs = PaymentOrder.objects.filter(
            merchant=merchant, is_deleted=False
        ).select_related("merchant")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class MerchantRefundViewSet(viewsets.GenericViewSet):
    """商户侧退款。"""
    authentication_classes = [HMACAuthentication]
    permission_classes = [HasHMACPrincipal]
    refund_service = RefundService()

    @action(detail=False, methods=["post"], url_path="apply")
    def apply_refund(self, request):
        """申请退款。"""
        serializer = RefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        merchant = getattr(request, "merchant", None)
        try:
            order = PaymentOrder.objects.get(
                order_no=data["order_no"],
                merchant=merchant,
                is_deleted=False,
            )
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
