"""商户管理 — API Views。"""
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db import models
from django.db.models import Prefetch
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.core.exceptions import BusinessException
from apps.rbac.authentication import JWTAuthentication
from apps.rbac.permissions import RequiresFeature
from .models import Merchant, MerchantKYC, MerchantFee, MerchantSettlementAccount, MerchantPaymentProduct, MerchantSplitConfig
from .serializers import (
    MerchantSerializer, MerchantListSerializer, MerchantKYCSerializer,
    MerchantFeeSerializer, SettlementAccountSerializer, PaymentProductSerializer,
    MerchantSplitConfigSerializer, MerchantStatusActionSerializer,
    MerchantKYCReviewSerializer,
)
from .services import MerchantLifecycleService, MerchantService


class MerchantViewSet(RequiresFeature, viewsets.ModelViewSet):
    """商户管理 ViewSet。"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    feature_code = "feature:merchants"
    ACTION_FEATURES = {
        "review_kyc": "feature:merchants.approve",
        "activate": "feature:merchants.approve",
        "suspend": "feature:merchants.approve",
        "close": "feature:merchants.approve",
        "update_risk_level": "feature:merchants.approve",
        "update_sanction_status": "feature:merchants.approve",
    }
    queryset = Merchant.objects.filter(is_deleted=False)
    serializer_class = MerchantSerializer
    lookup_field = "merchant_no"
    lookup_url_kwarg = "merchant_no"
    service = MerchantService()

    def perform_update(self, serializer):
        """更新商户时，若风险等级变更且未显式传入 next_review_date，自动计算复审周期。"""
        instance = serializer.instance
        risk_level = serializer.validated_data.get("risk_level", instance.risk_level)
        next_review = serializer.validated_data.get("next_review_date")

        # 风险等级变更 且 用户未手动设置复审日期 → 自动计算
        if risk_level != instance.risk_level and next_review is None:
            review_months = {"LOW": 12, "MEDIUM": 6, "HIGH": 3, "BLOCKED": 1}
            months = review_months.get(risk_level, 6)
            serializer.validated_data["next_review_date"] = date.today() + relativedelta(months=months)

        # 自动计算距到期天数
        license_expiry = serializer.validated_data.get(
            "license_expiry_date", instance.license_expiry_date
        )
        if license_expiry:
            serializer.validated_data["days_to_expiry"] = (license_expiry - date.today()).days

        serializer.save()

    def perform_destroy(self, instance):
        """软删除 — 设置 is_deleted=True 而非物理删除。"""
        actor = str(getattr(self.request.user, "id", ""))
        if instance.status != Merchant.Status.CLOSED:
            instance = MerchantLifecycleService().close(
                instance,
                reason_code="MERCHANT_DELETED",
                comment="运营人员删除商户",
                actor=actor,
                source="ADMIN_API",
            )
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted", "updated_at"])

    def get_queryset(self):
        from apps.user_portal.models import EndUser

        queryset = super().get_queryset().prefetch_related(
            "nostro_accounts",
            Prefetch(
                "enduser_set",
                queryset=EndUser.objects.filter(is_deleted=False).only(
                    "id", "username", "default_merchant_id"
                ),
                to_attr="linked_users",
            ),
        )
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                models.Q(merchant_name__icontains=search)
                | models.Q(merchant_no__icontains=search)
                | models.Q(contact_name__icontains=search)
                | models.Q(legal_person_name__icontains=search)
                | models.Q(kyc__legal_person__icontains=search)
                | models.Q(kyc__id_number_plain__icontains=search)
                | models.Q(enduser__username__icontains=search)
                | models.Q(enduser__email__icontains=search)
            ).distinct()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        risk_level = self.request.query_params.get("risk_level")
        if risk_level:
            queryset = queryset.filter(risk_level=risk_level)
        kyc_status = self.request.query_params.get("kyc_status")
        if kyc_status:
            queryset = queryset.filter(kyc__kyc_status=kyc_status)
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return MerchantListSerializer
        return MerchantSerializer

    @action(detail=False, methods=["get"], url_path="remittance-options")
    def remittance_options(self, request):
        """轻量汇款商户选项；不可用商户返回阻断原因供界面禁用。"""
        from apps.payment.services.remittance_policy import RemittanceEligibilityPolicy

        queryset = Merchant.objects.filter(is_deleted=False).select_related(
            "kyc", "agent"
        ).prefetch_related(
            Prefetch(
                "payment_products",
                queryset=MerchantPaymentProduct.objects.filter(
                    product_type=MerchantFee.ProductType.WIRE_TRANSFER,
                    is_deleted=False,
                ),
                to_attr="_remittance_products",
            ),
            Prefetch(
                "settlement_accounts",
                queryset=MerchantSettlementAccount.objects.filter(
                    is_default=True, is_deleted=False
                ),
                to_attr="_default_settlement_accounts",
            ),
        )
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                models.Q(merchant_no__icontains=search)
                | models.Q(merchant_name__icontains=search)
            )
        total = queryset.count()
        try:
            limit = min(max(int(request.query_params.get("limit", 50)), 1), 100)
        except (TypeError, ValueError):
            raise BusinessException("PARAM_INVALID", "The limit parameter must be an integer", 400)
        policy = RemittanceEligibilityPolicy()
        results = []
        for merchant in queryset[:limit]:
            decision = policy.evaluate(merchant, include_usage=False)
            results.append({
                "merchant_no": merchant.merchant_no,
                "merchant_name": merchant.merchant_name,
                "status": merchant.status,
                "status_label": merchant.get_status_display(),
                "kyc_status": getattr(getattr(merchant, "kyc", None), "kyc_status", ""),
                **decision.as_dict(),
            })
        return Response({"count": total, "results": results})

    # ── KYC ─────────────────────────────────────────────────

    @action(detail=True, methods=["put"], url_path="kyc")
    def set_kyc(self, request, merchant_no=None):
        merchant = self.get_object()
        serializer = MerchantKYCSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.service.set_kyc(merchant, serializer.validated_data)
        return Response({"message": "Customer due diligence particulars have been saved"})

    @action(detail=True, methods=["get"], url_path="kyc")
    def get_kyc(self, request, merchant_no=None):
        merchant = self.get_object()
        data = self.service.get_kyc(merchant)
        return Response(data)

    @action(detail=True, methods=["post"], url_path="review-kyc")
    def review_kyc(self, request, merchant_no=None):
        """第二级审核：原子完成 KYC、产品费率配置与激活。"""
        merchant = self.get_object()
        serializer = MerchantKYCReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        kyc = self.service.review_kyc(
            merchant,
            serializer.validated_data,
            actor=str(getattr(request.user, "id", "")),
        )
        merchant.refresh_from_db()
        return Response({
            "message": "Customer due diligence has been approved and the customer has been activated"
            if kyc.kyc_status == MerchantKYC.Status.APPROVED
            else "Customer due diligence has been rejected",
            "kyc_status": kyc.kyc_status,
            "merchant_status": merchant.status,
        })

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, merchant_no=None):
        serializer = MerchantStatusActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        merchant = MerchantLifecycleService().activate(
            self.get_object(),
            reason_code="MANUAL_ACTIVATION",
            comment=serializer.validated_data["reason"],
            actor=str(getattr(request.user, "id", "")),
            source="ADMIN_API",
        )
        return Response({"message": "The customer has been activated", "status": merchant.status})

    @action(detail=True, methods=["post"], url_path="suspend")
    def suspend(self, request, merchant_no=None):
        serializer = MerchantStatusActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        merchant = MerchantLifecycleService().suspend(
            self.get_object(),
            reason_code="MANUAL_SUSPENSION",
            comment=serializer.validated_data["reason"],
            actor=str(getattr(request.user, "id", "")),
            source="ADMIN_API",
        )
        return Response({"message": "The customer has been suspended", "status": merchant.status})

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, merchant_no=None):
        serializer = MerchantStatusActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        merchant = MerchantLifecycleService().close(
            self.get_object(),
            reason_code="MANUAL_CLOSURE",
            comment=serializer.validated_data["reason"],
            actor=str(getattr(request.user, "id", "")),
            source="ADMIN_API",
        )
        return Response({"message": "The customer has been closed", "status": merchant.status})

    # ── 风险管理 ────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="update-risk-level")
    def update_risk_level(self, request, merchant_no=None):
        """更新商户风险等级。"""
        merchant = self.get_object()
        risk_level = request.data.get("risk_level")
        valid_levels = ["LOW", "MEDIUM", "HIGH", "BLOCKED"]
        if risk_level not in valid_levels:
            return Response(
                {"detail": f"risk_level must be one of {valid_levels}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        merchant.risk_level = risk_level
        merchant.save(update_fields=["risk_level", "updated_at"])
        if risk_level == "BLOCKED" and merchant.status == Merchant.Status.ACTIVE:
            merchant = MerchantLifecycleService().suspend(
                merchant,
                reason_code="RISK_BLOCKED",
                comment="风险等级已调整为 BLOCKED",
                actor=str(getattr(request.user, "id", "")),
                source="RISK_REVIEW",
            )
        return Response({
            "message": "The risk rating has been updated",
            "risk_level": merchant.risk_level,
            "merchant_status": merchant.status,
        })

    @action(detail=True, methods=["post"], url_path="update-sanction-status")
    def update_sanction_status(self, request, merchant_no=None):
        """更新商户制裁名单状态。"""
        merchant = self.get_object()
        sanction_status = request.data.get("sanction_status")
        valid_statuses = ["UN", "OFAC"]
        if sanction_status not in valid_statuses:
            return Response(
                {"detail": f"sanction_status must be one of {valid_statuses}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        merchant.sanction_status = sanction_status
        merchant.save(update_fields=["sanction_status", "updated_at"])
        if sanction_status != "UN" and merchant.status == Merchant.Status.ACTIVE:
            merchant = MerchantLifecycleService().suspend(
                merchant,
                reason_code="SANCTION_RESTRICTION",
                comment=f"制裁状态变更为 {sanction_status}",
                actor=str(getattr(request.user, "id", "")),
                source="SANCTION_REVIEW",
            )
        return Response({
            "message": "The sanctions status has been updated",
            "sanction_status": merchant.sanction_status,
            "merchant_status": merchant.status,
        })

    # ── 手续费 ──────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="fees")
    def set_fee(self, request, merchant_no=None):
        merchant = self.get_object()
        serializer = MerchantFeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fee = self.service.set_fee(merchant, serializer.validated_data)
        return Response(MerchantFeeSerializer(fee).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="fees")
    def list_fees(self, request, merchant_no=None):
        merchant = self.get_object()
        fees = merchant.fees.filter(is_deleted=False)
        return Response(MerchantFeeSerializer(fees, many=True).data)

    # ── 结算账户 ────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="settlement-accounts")
    def set_settlement_account(self, request, merchant_no=None):
        merchant = self.get_object()
        serializer = SettlementAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = self.service.set_settlement_account(merchant, serializer.validated_data)
        return Response(SettlementAccountSerializer(account).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="settlement-accounts")
    def list_settlement_accounts(self, request, merchant_no=None):
        merchant = self.get_object()
        accounts = merchant.settlement_accounts.filter(is_deleted=False)
        return Response(SettlementAccountSerializer(accounts, many=True).data)

    # ── 支付产品 ────────────────────────────────────────────

    @action(detail=True, methods=["put"], url_path="payment-products")
    def set_payment_product(self, request, merchant_no=None):
        merchant = self.get_object()
        serializer = PaymentProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = self.service.set_payment_product(merchant, serializer.validated_data)
        return Response(PaymentProductSerializer(product).data)

    @action(detail=True, methods=["get"], url_path="payment-products")
    def list_payment_products(self, request, merchant_no=None):
        merchant = self.get_object()
        products = merchant.payment_products.filter(is_deleted=False)
        return Response(PaymentProductSerializer(products, many=True).data)

    @action(detail=True, methods=["get", "put"], url_path="split-config")
    def split_config(self, request, merchant_no=None):
        merchant = self.get_object()
        if request.method == "GET":
            cfg, _ = MerchantSplitConfig.objects.get_or_create(merchant=merchant)
            return Response(MerchantSplitConfigSerializer(cfg).data)
        ser = MerchantSplitConfigSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        cfg, _ = MerchantSplitConfig.objects.update_or_create(
            merchant=merchant, defaults=ser.validated_data
        )
        return Response(MerchantSplitConfigSerializer(cfg).data)

    @action(detail=True, methods=["get"], url_path="pending-funds")
    def pending_funds(self, request, merchant_no=None):
        from apps.settlement.models import SettlementBatch, SettlementDetail
        from apps.settlement.serializers import SettlementDetailSerializer
        merchant = self.get_object()
        batches = SettlementBatch.objects.filter(merchant=merchant, status="PENDING", is_deleted=False)
        details = SettlementDetail.objects.filter(batch__in=batches).select_related("batch")
        return Response(SettlementDetailSerializer(details, many=True).data)

    @action(detail=True, methods=["get"], url_path="settled-funds")
    def settled_funds(self, request, merchant_no=None):
        from apps.settlement.models import SettlementBatch, SettlementDetail
        from apps.settlement.serializers import SettlementDetailSerializer
        merchant = self.get_object()
        batches = SettlementBatch.objects.filter(merchant=merchant, status="SETTLED", is_deleted=False)
        details = SettlementDetail.objects.filter(batch__in=batches).select_related("batch")
        return Response(SettlementDetailSerializer(details, many=True).data)

    @action(detail=True, methods=["get"], url_path="pending-orders")
    def pending_orders(self, request, merchant_no=None):
        from apps.payment.models import PaymentOrder
        from apps.payment.serializers import PaymentOrderListSerializer
        merchant = self.get_object()
        orders = PaymentOrder.objects.filter(
            merchant=merchant, status="PENDING_SETTLE", is_deleted=False
        )
        return Response(PaymentOrderListSerializer(orders, many=True).data)

    @action(detail=True, methods=["get"], url_path="settled-orders")
    def settled_orders(self, request, merchant_no=None):
        from apps.payment.models import PaymentOrder
        from apps.payment.serializers import PaymentOrderListSerializer
        merchant = self.get_object()
        orders = PaymentOrder.objects.filter(
            merchant=merchant, status="SETTLED", is_deleted=False
        )
        return Response(PaymentOrderListSerializer(orders, many=True).data)

    @action(detail=True, methods=["get"], url_path="settled-funds-export")
    def settled_funds_export(self, request, merchant_no=None):
        from apps.settlement.models import SettlementBatch, SettlementDetail
        from apps.core.excel_export import excel_response
        merchant = self.get_object()
        batches = SettlementBatch.objects.filter(merchant=merchant, status="SETTLED", is_deleted=False)
        details = SettlementDetail.objects.filter(batch__in=batches).select_related("batch")
        rows = [(d.order_no, str(d.amount), str(d.fee), str(d.settle_amount), d.batch.batch_no) for d in details]
        return excel_response(["订单号", "金额", "手续费", "结算金额", "批次号"], rows, f"settled_funds_{merchant.merchant_no}.xlsx")

    @action(detail=True, methods=["get"], url_path="settled-orders-export")
    def settled_orders_export(self, request, merchant_no=None):
        from apps.payment.models import PaymentOrder
        from apps.core.excel_export import excel_response
        merchant = self.get_object()
        orders = PaymentOrder.objects.filter(merchant=merchant, status="SETTLED", is_deleted=False)
        rows = [(o.order_no, o.merchant_order_no, str(o.amount), str(o.fee_amount), o.status) for o in orders]
        return excel_response(["平台订单号", "商户订单号", "金额", "手续费", "状态"], rows, f"settled_orders_{merchant.merchant_no}.xlsx")

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        qs = Merchant.objects.filter(is_deleted=False)
        kyc_qs = MerchantKYC.objects.filter(is_deleted=False)
        today = date.today()
        expiring = qs.filter(
            license_expiry_date__isnull=False,
            license_expiry_date__lte=today + relativedelta(days=30),
            license_expiry_date__gte=today,
        ).count()
        return Response({
            "total": qs.count(),
            "pending_kyc": kyc_qs.filter(kyc_status="PENDING").count(),
            "approved_kyc": kyc_qs.filter(kyc_status="APPROVED").count(),
            "rejected_kyc": kyc_qs.filter(kyc_status="REJECTED").count(),
            "low_risk": qs.filter(risk_level="LOW").count(),
            "medium_risk": qs.filter(risk_level="MEDIUM").count(),
            "high_risk": qs.filter(risk_level="HIGH").count(),
            "expiring_30": expiring,
        })
