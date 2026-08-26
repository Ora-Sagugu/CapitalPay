"""商户管理 — API Views。"""
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db import models
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.core.exceptions import BusinessException, ErrorCode
from apps.rbac.permissions import require_permission
from .models import Merchant, MerchantKYC, MerchantFee, MerchantSettlementAccount, MerchantPaymentProduct
from .serializers import (
    MerchantSerializer, MerchantListSerializer, MerchantKYCSerializer,
    MerchantFeeSerializer, SettlementAccountSerializer, PaymentProductSerializer,
)
from .services import MerchantService


class MerchantViewSet(viewsets.ModelViewSet):
    """商户管理 ViewSet。"""
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
        instance.is_deleted = True
        instance.status = "CLOSED"
        instance.save(update_fields=["is_deleted", "status", "updated_at"])

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related("nostro_accounts")
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                models.Q(merchant_name__icontains=search)
                | models.Q(merchant_no__icontains=search)
                | models.Q(contact_name__icontains=search)
            )
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        risk_level = self.request.query_params.get("risk_level")
        if risk_level:
            queryset = queryset.filter(risk_level=risk_level)
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return MerchantListSerializer
        return MerchantSerializer

    # ── KYC ─────────────────────────────────────────────────

    @action(detail=True, methods=["put"], url_path="kyc")
    def set_kyc(self, request, merchant_no=None):
        merchant = self.get_object()
        serializer = MerchantKYCSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.service.set_kyc(merchant, serializer.validated_data)
        return Response({"message": "KYC 设置成功"})

    @action(detail=True, methods=["get"], url_path="kyc")
    def get_kyc(self, request, merchant_no=None):
        merchant = self.get_object()
        data = self.service.get_kyc(merchant)
        return Response(data)

    @action(detail=True, methods=["post"], url_path="review-kyc")
    @require_permission("merchant:approve")
    def review_kyc(self, request, merchant_no=None):
        """审核 KYC — approve/reject。
        Approve 时可选设置: risk_level, max_single_amount, daily_limit, fixed_fee
        Reject 时需提供: reason
        """
        merchant = self.get_object()
        action_type = request.data.get("action")
        if action_type not in ("approve", "reject"):
            return Response(
                {"detail": "action 必须为 approve 或 reject"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            kyc = merchant.kyc
        except MerchantKYC.DoesNotExist:
            return Response(
                {"detail": "商户尚未提交 KYC 信息"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if action_type == "reject":
            reason = request.data.get("reason", "").strip()
            if not reason:
                return Response(
                    {"detail": "拒绝时必须提供拒绝原因"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            kyc.kyc_status = "REJECTED"
            kyc.remark = reason
            kyc.reviewed_at = timezone.now()
            kyc.save(update_fields=["kyc_status", "remark", "reviewed_at", "updated_at"])
            return Response({
                "message": "KYC 已拒绝",
                "kyc_status": kyc.kyc_status,
                "reason": reason,
            })

        # action_type == "approve"
        kyc.kyc_status = "APPROVED"
        kyc.reviewed_at = timezone.now()
        kyc.save(update_fields=["kyc_status", "reviewed_at", "updated_at"])

        # 可选：设置商户风险等级、限额、费用
        updates = {}
        for field in ["risk_level", "max_single_amount", "daily_count", "daily_limit", "fixed_fee", "fee_rate"]:
            value = request.data.get(field)
            if value is not None:
                updates[field] = value
        if updates:
            for field, value in updates.items():
                setattr(merchant, field, value)
            # 风险等级变更时自动计算复审日
            if "risk_level" in updates:
                review_months = {"LOW": 12, "MEDIUM": 6, "HIGH": 3, "BLOCKED": 1}
                months = review_months.get(updates["risk_level"], 6)
                merchant.next_review_date = date.today() + relativedelta(months=months)
                updates["next_review_date"] = merchant.next_review_date
            merchant.save(update_fields=list(updates.keys()) + ["updated_at"])

        # 设置商户状态为 ACTIVE
        if merchant.status != "ACTIVE":
            merchant.status = "ACTIVE"
            merchant.save(update_fields=["status", "updated_at"])

        return Response({
            "message": "KYC 已通过",
            "kyc_status": kyc.kyc_status,
            "merchant_updates": updates,
        })

    # ── 风险管理 ────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="update-risk-level")
    def update_risk_level(self, request, merchant_no=None):
        """更新商户风险等级。"""
        merchant = self.get_object()
        risk_level = request.data.get("risk_level")
        valid_levels = ["LOW", "MEDIUM", "HIGH", "BLOCKED"]
        if risk_level not in valid_levels:
            return Response(
                {"detail": f"risk_level 必须为 {valid_levels} 之一"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        merchant.risk_level = risk_level
        merchant.save(update_fields=["risk_level", "updated_at"])
        return Response({"message": "风险等级已更新", "risk_level": merchant.risk_level})

    @action(detail=True, methods=["post"], url_path="update-sanction-status")
    def update_sanction_status(self, request, merchant_no=None):
        """更新商户制裁名单状态。"""
        merchant = self.get_object()
        sanction_status = request.data.get("sanction_status")
        valid_statuses = ["UN", "OFAC", "EU", "HMT"]
        if sanction_status not in valid_statuses:
            return Response(
                {"detail": f"sanction_status 必须为 {valid_statuses} 之一"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        merchant.sanction_status = sanction_status
        merchant.save(update_fields=["sanction_status", "updated_at"])
        return Response({"message": "制裁状态已更新", "sanction_status": merchant.sanction_status})

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
