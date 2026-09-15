"""用户端 API 视图 — 注册、登录、账户绑定、交易查询、支付发起、首次登录资料。"""
from django.db.models import Q
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import BusinessException
from apps.rbac.authentication import JWTAuthentication
from apps.rbac.permissions import RequiresFeature
from .models import EndUser, UserOnboarding
from .serializers import (
    RegisterSerializer, RegisterByEmailSerializer,
    LoginByPasswordSerializer, LoginByEmailSerializer, LoginBySmsSerializer,
    SmsCodeSerializer, ResetPasswordSerializer, RefreshTokenSerializer,
    ProfileUpdateSerializer, IdentityVerifySerializer, ChooseRoleSerializer,
    OnboardingSubmitSerializer, OnboardingReviewSerializer, AgentOrderReviewSerializer,
    AgentRemittanceQuoteSerializer, AgentRemittanceSubmitSerializer,
    BindMerchantSerializer,
)
from .services import UserService


class UserAuthViewSet(viewsets.ViewSet):
    """用户端认证 — 注册、登录、短信验证码。"""
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    service = UserService()

    @action(methods=["post"], detail=False, url_path="register")
    def register(self, request):
        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = self.service.register(**s.validated_data)
        return Response(result, status=status.HTTP_201_CREATED)

    @action(methods=["post"], detail=False, url_path="register-email")
    def register_email(self, request):
        s = RegisterByEmailSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = self.service.register_by_email(**s.validated_data)
        return Response(result, status=status.HTTP_201_CREATED)

    @action(methods=["post"], detail=False, url_path="login/password")
    def login_password(self, request):
        s = LoginByPasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        ip = request.META.get("REMOTE_ADDR", "")
        result = self.service.login_by_password(
            phone=s.validated_data["phone"],
            password=s.validated_data["password"],
            ip=ip,
            portal_role=s.validated_data.get("portal_role") or "",
        )
        return Response(result)

    @action(methods=["post"], detail=False, url_path="login/email")
    def login_email(self, request):
        s = LoginByEmailSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        ip = request.META.get("REMOTE_ADDR", "")
        result = self.service.login_by_email(
            email=s.validated_data["email"],
            password=s.validated_data["password"],
            ip=ip,
            portal_role=s.validated_data.get("portal_role") or "",
        )
        return Response(result)

    @action(methods=["post"], detail=False, url_path="login/sms")
    def login_sms(self, request):
        s = LoginBySmsSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        ip = request.META.get("REMOTE_ADDR", "")
        result = self.service.login_by_sms(
            phone=s.validated_data["phone"],
            sms_code=s.validated_data["sms_code"],
            ip=ip,
            portal_role=s.validated_data.get("portal_role") or "",
        )
        return Response(result)

    @action(methods=["post"], detail=False, url_path="sms/send")
    def send_sms(self, request):
        s = SmsCodeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = self.service.send_sms_code(
            phone=s.validated_data["phone"],
            scene=s.validated_data["scene"],
        )
        return Response(result)

    @action(methods=["post"], detail=False, url_path="refresh")
    def refresh(self, request):
        s = RefreshTokenSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = self.service.refresh_token(s.validated_data["refresh_token"])
        return Response(result)


class UserProfileViewSet(viewsets.ViewSet):
    """用户个人中心 — 资料查看、修改、实名认证。"""
    authentication_classes = [JWTAuthentication]

    @action(methods=["get"], detail=False, url_path="me")
    def me(self, request):
        """获取当前登录用户的完整资料。"""
        user = self._get_user(request)
        service = UserService()
        return Response(service.get_profile(user))

    @action(methods=["put"], detail=False, url_path="update")
    def update_profile(self, request):
        user = self._get_user(request)
        s = ProfileUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        service = UserService()
        service.update_profile(user, **s.validated_data)
        return Response({"message": "The profile has been updated"})

    @action(methods=["post"], detail=False, url_path="choose-role")
    def choose_role(self, request):
        user = self._get_user(request)
        s = ChooseRoleSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(UserService().choose_role(user, s.validated_data["role"]))

    @action(methods=["post"], detail=False, url_path="verify")
    def verify_identity(self, request):
        user = self._get_user(request)
        s = IdentityVerifySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        service = UserService()
        service.verify_identity(
            user,
            real_name=s.validated_data["real_name"],
            id_card=s.validated_data["id_card"],
        )
        return Response({"message": "Identity verification has been completed"})

    @action(methods=["post"], detail=False, url_path="reset-password")
    def reset_password(self, request):
        s = ResetPasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        service = UserService()
        service.reset_password(
            phone=s.validated_data["phone"],
            sms_code=s.validated_data["sms_code"],
            new_password=s.validated_data["new_password"],
        )
        return Response({"message": "The password has been reset"})

    def _get_user(self, request) -> EndUser:
        if not request.user or not isinstance(request.user, EndUser):
            raise BusinessException("UNAUTHORIZED", "Authentication credentials are required", 401)
        return request.user


class UserAgentViewSet(viewsets.ViewSet):
    """Agent self-service — profile, referred KYC, and remittance agree/reject."""
    authentication_classes = [JWTAuthentication]
    service = UserService()

    @action(methods=["get"], detail=False, url_path="me")
    def me(self, request):
        user = self._get_user(request)
        return Response(self.service.get_bound_agent_profile(user))

    @action(methods=["get"], detail=False, url_path="accounts/currencies")
    def account_currencies(self, request):
        from apps.core.currencies import list_currencies

        self.service.require_bound_agent(self._get_user(request))
        return Response({"items": list_currencies()})

    @action(methods=["post"], detail=False, url_path="accounts/enable")
    def account_enable(self, request):
        user = self._get_user(request)
        return Response(self.service.enable_bound_agent_currency(
            user, request.data.get("currency", ""),
        ))

    @action(methods=["get", "post"], detail=False, url_path="accounts/deposits")
    def account_deposits(self, request):
        user = self._get_user(request)
        if request.method == "GET":
            return Response(self.service.list_bound_agent_deposits(
                user,
                page=request.query_params.get("page", 1),
                page_size=request.query_params.get("page_size", 20),
            ))
        return Response(
            self.service.create_bound_agent_deposit(
                user,
                currency=request.data.get("currency", ""),
                amount=request.data.get("amount"),
                remark=request.data.get("remark", ""),
            ),
            status=status.HTTP_201_CREATED,
        )

    @action(methods=["get"], detail=False, url_path="accounts")
    def accounts(self, request):
        user = self._get_user(request)
        return Response(self.service.list_bound_agent_currency_accounts(user))

    @action(methods=["get"], detail=False, url_path="merchants")
    def merchants(self, request):
        user = self._get_user(request)
        items = self.service.list_bound_agent_merchants(user)
        return Response({"total": len(items), "items": items})

    @action(methods=["get"], detail=False, url_path="virtual-accounts")
    def virtual_accounts(self, request):
        user = self._get_user(request)
        return Response(self.service.list_bound_customer_virtual_accounts(
            user,
            search=request.query_params.get("search") or "",
            status=request.query_params.get("status") or "",
            page=request.query_params.get("page", 1),
            page_size=request.query_params.get("page_size", 20),
        ))

    @action(methods=["get"], detail=False, url_path="virtual-accounts/stats")
    def virtual_account_stats(self, request):
        user = self._get_user(request)
        return Response(self.service.bound_customer_virtual_account_stats(user))

    @action(methods=["get"], detail=False, url_path=r"virtual-accounts/(?P<va_id>[^/.]+)/transactions")
    def virtual_account_transactions(self, request, va_id=None):
        user = self._get_user(request)
        return Response(self.service.get_bound_customer_va_transactions(user, va_id))

    @action(methods=["get"], detail=False, url_path="kyc")
    def kyc_list(self, request):
        user = self._get_user(request)
        return Response(self.service.list_agent_kyc(
            user,
            stage=request.query_params.get("stage") or "",
            search=request.query_params.get("search") or "",
            page=request.query_params.get("page", 1),
            page_size=request.query_params.get("page_size", 20),
        ))

    @action(methods=["get"], detail=False, url_path=r"kyc/(?P<user_id>[^/.]+)")
    def kyc_detail(self, request, user_id=None):
        user = self._get_user(request)
        return Response(self.service.get_agent_kyc_detail(user, user_id))

    @action(methods=["post"], detail=False, url_path=r"kyc/(?P<user_id>[^/.]+)/review")
    def kyc_review(self, request, user_id=None):
        user = self._get_user(request)
        s = OnboardingReviewSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        reviewer_name = getattr(user, "username", "") or getattr(user, "nickname", "")
        return Response(self.service.review_agent_kyc(
            user,
            user_id,
            action=s.validated_data["action"],
            remark=s.validated_data.get("remark", ""),
            reviewer=reviewer_name,
        ))

    @action(methods=["get"], detail=False, url_path="earnings")
    def earnings(self, request):
        user = self._get_user(request)
        page = request.query_params.get("page", 1)
        page_size = request.query_params.get("page_size", 20)
        period = request.query_params.get("period") or "month"
        merchant_name = request.query_params.get("merchant_name") or ""
        return Response(self.service.list_bound_agent_earnings(
            user,
            page=page,
            page_size=page_size,
            period=period,
            merchant_name=merchant_name,
        ))

    @action(methods=["get"], detail=False, url_path="orders")
    def orders_list(self, request):
        user = self._get_user(request)
        return Response(self.service.list_agent_orders(
            user,
            stage=request.query_params.get("stage") or "",
            search=request.query_params.get("search") or "",
            page=request.query_params.get("page", 1),
            page_size=request.query_params.get("page_size", 20),
        ))

    @action(methods=["get"], detail=False, url_path=r"orders/(?P<order_no>[^/.]+)")
    def orders_detail(self, request, order_no=None):
        user = self._get_user(request)
        return Response(self.service.get_agent_order(user, order_no))

    @action(methods=["post"], detail=False, url_path=r"orders/(?P<order_no>[^/.]+)/review")
    def orders_review(self, request, order_no=None):
        user = self._get_user(request)
        s = AgentOrderReviewSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        reviewer_name = getattr(user, "username", "") or getattr(user, "nickname", "")
        return Response(self.service.review_agent_order(
            user,
            order_no,
            action=s.validated_data["action"],
            remark=s.validated_data.get("remark", ""),
            reviewer=reviewer_name,
        ))

    @action(methods=["post"], detail=False, url_path=r"orders/(?P<order_no>[^/.]+)/request-payout")
    def orders_request_payout(self, request, order_no=None):
        user = self._get_user(request)
        reviewer_name = getattr(user, "username", "") or getattr(user, "nickname", "")
        return Response(self.service.request_agent_payout(
            user,
            order_no,
            reviewer=reviewer_name,
        ))

    @action(methods=["get"], detail=False, url_path="fund-transfers/accounts")
    def fund_transfer_accounts(self, request):
        user = self._get_user(request)
        items = self.service.list_bound_agent_nostro_accounts(user)
        return Response({"total": len(items), "items": items})

    @action(methods=["get", "post"], detail=False, url_path="fund-transfers")
    def fund_transfers(self, request):
        user = self._get_user(request)
        if request.method == "GET":
            return Response(self.service.list_bound_agent_fund_transfers(
                user,
                page=request.query_params.get("page", 1),
                page_size=request.query_params.get("page_size", 50),
            ))
        return Response(
            self.service.create_bound_agent_fund_transfer(
                user,
                from_account_id=request.data.get("from_account"),
                to_account_id=request.data.get("to_account"),
                amount=request.data.get("amount"),
                remark=request.data.get("remark", ""),
            ),
            status=status.HTTP_201_CREATED,
        )

    @action(methods=["post"], detail=False, url_path=r"fund-transfers/(?P<transfer_no>[^/.]+)/execute")
    def fund_transfer_execute(self, request, transfer_no=None):
        user = self._get_user(request)
        return Response(self.service.execute_bound_agent_fund_transfer(user, transfer_no))

    @action(methods=["post"], detail=False, url_path="payments/quote")
    def payments_quote(self, request):
        """Agent quotes remittance on behalf of a bound customer merchant."""
        user = self._get_user(request)
        s = AgentRemittanceQuoteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        quote = self.service.create_agent_remittance_quote(
            user,
            merchant_id=data["merchant_id"],
            amount=data["amount"],
            from_currency=data["from_currency"],
            to_currency=data["to_currency"],
            fee_bearing=data["fee_bearing"],
        )
        return Response(quote, status=status.HTTP_201_CREATED)

    @action(methods=["post"], detail=False, url_path="payments/apply")
    def payments_apply(self, request):
        """Agent submits remittance on behalf of a bound customer merchant."""
        user = self._get_user(request)
        s = AgentRemittanceSubmitSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        merchant_id = data.pop("merchant_id")
        from apps.payment.serializers import PaymentOrderSerializer
        order, created = self.service.submit_agent_remittance(
            user,
            merchant_id=merchant_id,
            payload=data,
            idempotency_key=request.headers.get("Idempotency-Key", ""),
        )
        return Response(
            PaymentOrderSerializer(order).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(methods=["post"], detail=False, url_path="payments/sanction-check")
    def payments_sanction_check(self, request):
        """Lightweight beneficiary sanction scan for agent remittance form."""
        user = self._get_user(request)
        self.service.require_bound_agent(user)
        beneficiary_name = (request.data.get("beneficiary_name") or "").strip()
        beneficiary_address = (request.data.get("beneficiary_address") or "").strip()
        from apps.compliance.services import scan_entity_lightweight, build_sanction_warning
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
            "warning_message": "" if result["is_clear"] else build_sanction_warning(
                result["name_hits"], result["address_hits"], result.get("country_hits", [])
            ),
        })

    def _get_user(self, request) -> EndUser:
        if not request.user or not isinstance(request.user, EndUser):
            raise BusinessException("UNAUTHORIZED", "Authentication credentials are required", 401)
        return request.user


class UserOnboardingViewSet(viewsets.ViewSet):
    """用户首次登录资料 — 三步向导提交与查询。"""
    authentication_classes = [JWTAuthentication]
    service = UserService()

    @action(methods=["post"], detail=False, url_path="submit")
    def submit(self, request):
        user = self._get_user(request)
        s = OnboardingSubmitSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = self.service.submit_onboarding(user, s.validated_data)
        return Response(result)

    @action(methods=["get"], detail=False, url_path="status")
    def status(self, request):
        user = self._get_user(request)
        onboarding = self.service.get_onboarding(user)
        review = self.service.agent_review_payload(user)
        return Response({
            "onboarding_status": user.onboarding_status,
            "submitted_at": user.onboarding_submitted_at,
            "reviewed_at": user.onboarding_reviewed_at,
            "reviewer": user.onboarding_reviewer,
            "remark": user.onboarding_remark,
            "data": onboarding,
            **review,
        })

    @action(methods=["post"], detail=False, url_path="upload")
    def upload(self, request):
        """证件图片上传，返回 media 相对路径。"""
        self._get_user(request)
        f = request.FILES.get("file")
        if not f:
            raise BusinessException("PARAM_MISSING", "A file must be selected")
        from django.core.files.storage import default_storage
        from django.utils import timezone
        name = f"kyc/{timezone.now().strftime('%Y%m%d')}/{f.name}"
        saved = default_storage.save(name, f)
        return Response({"path": saved, "url": default_storage.url(saved)})

    def _get_user(self, request) -> EndUser:
        if not request.user or not isinstance(request.user, EndUser):
            raise BusinessException("UNAUTHORIZED", "Authentication credentials are required", 401)
        return request.user


class UserOnboardingAdminViewSet(RequiresFeature, viewsets.ViewSet):
    """用户资料审核 — 运营后台使用。"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    feature_code = "feature:merchants"
    ACTION_FEATURES = {
        "start_review": "feature:merchants.approve",
        "review": "feature:merchants.approve",
        "toggle_status": "feature:merchants.approve",
    }
    service = UserService()

    def list(self, request):
        """GET /api/v1/admin/onboarding/ — 分页列表。"""
        return self.list_onboarding(request)

    @action(methods=["get"], detail=False, url_path="list")
    def list_onboarding(self, request):
        status_filter = request.query_params.get("status")
        stage = request.query_params.get("stage") or ""
        search = request.query_params.get("search", "")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        base = EndUser.objects.filter(is_deleted=False).exclude(
            onboarding_status="none"
        ).select_related(
            "default_merchant", "default_merchant__kyc",
            "default_agent", "default_agent__kyc",
            "onboarding",
        )

        pending_profile_q = Q(onboarding_status__in=["pending", "under_review"])
        waiting_agent_q = Q(onboarding__agent_review_status="pending")
        ops_pending_profile_q = pending_profile_q & ~waiting_agent_q
        pending_kyc_q = (
            Q(onboarding_status="approved", default_merchant__kyc__kyc_status="PENDING")
            | Q(onboarding_status="approved", default_agent__kyc__kyc_status="PENDING")
        )
        approved_q = (
            Q(default_merchant__kyc__kyc_status="APPROVED")
            | Q(default_agent__kyc__kyc_status="APPROVED")
        )
        rejected_q = (
            Q(onboarding_status="rejected")
            | Q(default_merchant__kyc__kyc_status="REJECTED")
            | Q(default_agent__kyc__kyc_status="REJECTED")
        )

        stats = {
            "pending_profile": base.filter(ops_pending_profile_q).count(),
            "pending_kyc": base.filter(pending_kyc_q).count(),
            "approved": base.filter(approved_q).count(),
            "rejected": base.filter(rejected_q).distinct().count(),
            "total": base.count(),
        }

        qs = base
        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
                | Q(real_name__icontains=search)
                | Q(onboarding__legal_name__icontains=search)
            )
        if stage == "profile_pending":
            qs = qs.filter(ops_pending_profile_q)
        elif stage == "kyc_pending":
            qs = qs.filter(pending_kyc_q)
        elif stage == "approved":
            qs = qs.filter(approved_q)
        elif stage == "rejected":
            qs = qs.filter(rejected_q).distinct()
        elif stage in ("", "needs_review"):
            qs = qs.filter(ops_pending_profile_q | pending_kyc_q)
        elif status_filter:
            qs = qs.filter(onboarding_status=status_filter)

        qs = qs.order_by("-onboarding_submitted_at")
        total = qs.count()
        items = qs[(page - 1) * page_size : page * page_size]
        data = []
        for user in items:
            merchant = user.default_merchant
            agent = user.default_agent
            kyc = getattr(merchant, "kyc", None) if merchant else None
            agent_kyc = getattr(agent, "kyc", None) if agent else None
            try:
                onboarding = user.onboarding
            except UserOnboarding.DoesNotExist:
                onboarding = None
            kyc_status = kyc.kyc_status if kyc else ""
            agent_kyc_status = agent_kyc.kyc_status if agent_kyc else ""
            legal_person = (
                (kyc.legal_person if kyc else "")
                or (agent_kyc.legal_person if agent_kyc else "")
                or (onboarding.legal_name if onboarding else "")
            )
            id_type = (
                (kyc.id_type if kyc else "")
                or (agent_kyc.id_type if agent_kyc else "")
                or (onboarding.id_type if onboarding else "")
            )
            portal_role = user.portal_role or "none"
            next_stage = ""
            if user.onboarding_status == "approved" and merchant and merchant.status == "PENDING":
                next_stage = "KYC_PENDING"
            elif (merchant and merchant.status == "ACTIVE") or (agent and agent.status == "ACTIVE"):
                next_stage = "ACTIVE"
            data.append({
                "id": str(user.id),
                "username": user.username,
                "name": user.real_name or user.nickname or user.username,
                "email": user.email,
                "phone": user.phone or "",
                "status": user.onboarding_status,
                "onboarding_status": user.onboarding_status,
                "portal_role": portal_role,
                "is_active": user.is_active,
                "submitted_at": user.onboarding_submitted_at,
                "reviewed_at": user.onboarding_reviewed_at,
                "reviewer": user.onboarding_reviewer,
                "remark": user.onboarding_remark,
                "legal_person": legal_person,
                "id_type": id_type,
                "merchant_no": merchant.merchant_no if merchant else "",
                "merchant_status": merchant.status if merchant else "",
                "merchant_kyc_status": kyc_status,
                "agent_no": agent.agent_no if agent else "",
                "agent_status": agent.status if agent else "",
                "agent_kyc_status": agent_kyc_status,
                "next_stage": next_stage,
            })
        return Response({
            "count": total,
            "results": data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": data,
            "stats": stats,
        })

    def retrieve(self, request, pk=None):
        user = EndUser.objects.filter(id=pk, is_deleted=False).first()
        if not user:
            raise BusinessException("USER_NOT_FOUND", "The user does not exist", 404)
        return Response({
            "id": str(user.id),
            "username": user.username,
            "status": user.onboarding_status,
            "onboarding_status": user.onboarding_status,
            "submitted_at": user.onboarding_submitted_at,
            "reviewed_at": user.onboarding_reviewed_at,
            "reviewer": user.onboarding_reviewer,
            "remark": user.onboarding_remark,
        })

    @action(methods=["post"], detail=True, url_path="start-review")
    def start_review(self, request, pk=None):
        """打开资料详情时，将 Pending review 标记为 Under review。"""
        user = EndUser.objects.filter(id=pk, is_deleted=False).first()
        if not user:
            raise BusinessException("USER_NOT_FOUND", "The user does not exist", 404)
        return Response(self.service.start_onboarding_review(user))

    @action(methods=["post"], detail=True, url_path="review")
    def review(self, request, pk=None):
        user = EndUser.objects.filter(id=pk, is_deleted=False).first()
        if not user:
            raise BusinessException("USER_NOT_FOUND", "The user does not exist", 404)

        s = OnboardingReviewSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        reviewer_name = getattr(request.user, "username", "")
        result = self.service.review_onboarding(
            user,
            action=s.validated_data["action"],
            remark=s.validated_data.get("remark", ""),
            reviewer=reviewer_name,
        )
        return Response(result)

    @action(methods=["post"], detail=True, url_path="toggle-status")
    def toggle_status(self, request, pk=None):
        """启停用与 onboarding 关联的终端用户。"""
        user = EndUser.objects.filter(id=pk, is_deleted=False).first()
        if not user:
            raise BusinessException("USER_NOT_FOUND", "The user does not exist", 404)
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        return Response({
            "message": "The user has been {}".format("enabled" if user.is_active else "disabled"),
            "is_active": user.is_active,
        })

    @action(methods=["get"], detail=True, url_path="detail")
    def onboarding_detail(self, request, pk=None):
        user = EndUser.objects.filter(id=pk, is_deleted=False).first()
        if not user:
            raise BusinessException("USER_NOT_FOUND", "The user does not exist", 404)

        onboarding = self.service.get_onboarding(user)
        return Response({
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "onboarding_status": user.onboarding_status,
            "portal_role": user.portal_role or "none",
            "submitted_at": user.onboarding_submitted_at,
            "reviewed_at": user.onboarding_reviewed_at,
            "reviewer": user.onboarding_reviewer,
            "remark": user.onboarding_remark,
            "data": onboarding,
        })


def _mask_account_number(value: str) -> str:
    from apps.report.metrics import mask_account

    return mask_account(value)


def _customer_virtual_account_rows(merchant=None):
    from apps.account.models import VirtualAccount

    if not merchant:
        return []
    rows = []
    vas = (
        VirtualAccount.objects.filter(merchant=merchant, is_deleted=False)
        .order_by("currency", "-created_at")
    )
    for va in vas:
        ccy = (va.currency or "").upper()
        if not ccy:
            continue
        rows.append({
            "id": str(va.id),
            "currency": ccy,
            "balance": f"{va.available_balance:.2f}",
            "ledger_balance": f"{va.ledger_balance:.2f}",
            "bank_code": va.bank_code or "",
            "bank_name": va.bank_name or "",
            "account_holder": va.account_holder or "",
            "account_number": _mask_account_number(va.va_number),
            "va_number": va.va_number or "",
            "status": va.status,
        })
    return rows


def _customer_virtual_account_payload(merchant=None):
    return {
        "merchant_name": merchant.merchant_name if merchant else "",
        "merchant_no": merchant.merchant_no if merchant else "",
        "virtual_accounts": _customer_virtual_account_rows(merchant),
    }


def _serialize_bound_account(acc):
    from apps.core.utils import decrypt_field

    raw_number = decrypt_field(acc.account_number) if acc.account_number else ""
    return {
        "id": str(acc.id),
        "source": "added",
        "bank_code": acc.bank_code,
        "bank_name": acc.bank_name,
        "account_holder": acc.account_holder,
        "account_number": _mask_account_number(raw_number),
        "status": acc.status,
        "merchant_name": acc.merchant.merchant_name if acc.merchant else "",
        "merchant_no": acc.merchant.merchant_no if acc.merchant else "",
        "bind_at": acc.bind_at,
        "expire_at": acc.expire_at,
    }


def _registration_account_payload(user, va_rows, claimed_bank_codes):
    """Bank card auto-created from onboarding Financial Details."""
    from apps.core.utils import decrypt_field
    from apps.merchant.models import MerchantSettlementAccount

    merchant = user.default_merchant
    onboarding = getattr(user, "onboarding", None)
    reg_balances = [
        {"currency": row["currency"], "balance": row["balance"]}
        for row in va_rows
        if not row.get("bank_code") or row["bank_code"] not in claimed_bank_codes
    ]

    if merchant:
        settlement = (
            MerchantSettlementAccount.objects.filter(merchant=merchant, is_deleted=False)
            .order_by("-is_default", "-created_at")
            .first()
        )
        if settlement:
            raw_number = settlement.account_number or ""
            try:
                raw_number = decrypt_field(raw_number) or raw_number
            except Exception:
                pass
            return {
                "id": str(settlement.id),
                "source": "registration",
                "bank_code": "",
                "bank_name": settlement.bank_name or "",
                "branch_name": settlement.bank_branch or "",
                "account_holder": settlement.account_name or "",
                "account_number": _mask_account_number(raw_number),
                "swift_code": (onboarding.swift_code if onboarding else "") or "",
                "status": "ACTIVE" if getattr(merchant, "status", "") == "ACTIVE" else (merchant.status or "ACTIVE"),
                "balances": reg_balances,
                "currency": reg_balances[0]["currency"] if reg_balances else "",
                "balance": reg_balances[0]["balance"] if reg_balances else "0.00",
                "can_unbind": False,
            }

    if onboarding and (onboarding.bank_name or onboarding.bank_account):
        return {
            "id": f"onboarding-{user.id}",
            "source": "registration",
            "bank_code": "",
            "bank_name": onboarding.bank_name or "",
            "branch_name": onboarding.branch_name or "",
            "account_holder": onboarding.account_name or onboarding.legal_name or "",
            "account_number": _mask_account_number(onboarding.bank_account or ""),
            "swift_code": onboarding.swift_code or "",
            "status": (user.onboarding_status or "pending").upper(),
            "balances": reg_balances,
            "currency": reg_balances[0]["currency"] if reg_balances else "",
            "balance": reg_balances[0]["balance"] if reg_balances else "0.00",
            "can_unbind": False,
        }
    return None


def _added_card_payload(acc, va_rows):
    payload = _serialize_bound_account(acc)
    matches = [row for row in va_rows if row.get("bank_code") == acc.bank_code]
    balances = [{"currency": row["currency"], "balance": row["balance"]} for row in matches]
    payload["balances"] = balances
    payload["currency"] = balances[0]["currency"] if balances else ""
    payload["balance"] = balances[0]["balance"] if balances else "0.00"
    payload["can_unbind"] = True
    return payload


def _customer_accounts_overview(user):
    from apps.account.models import UserAccount

    merchant = user.default_merchant
    va_rows = _customer_virtual_account_rows(merchant) if merchant else []
    bound = list(
        UserAccount.objects.filter(user_id=str(user.id), is_deleted=False)
        .exclude(status=UserAccount.BindStatus.REVOKED)
        .select_related("merchant")
        .order_by("-created_at")
    )
    claimed = {acc.bank_code for acc in bound if acc.bank_code}
    balances = [
        {"currency": row["currency"], "balance": row["balance"], "status": row.get("status", "")}
        for row in va_rows
    ]
    return {
        "registration": _registration_account_payload(user, va_rows, claimed),
        "added_cards": [_added_card_payload(acc, va_rows) for acc in bound],
        "balances": balances,
    }


class UserAccountViewSet(viewsets.ViewSet):
    """用户账户管理 — 银行账户绑定、解绑、查询。"""
    authentication_classes = [JWTAuthentication]

    @action(methods=["get"], detail=False, url_path="list")
    def list_accounts(self, request):
        """Accounts overview: registration Financial Details + added bank cards."""
        user = self._get_user(request)
        return Response(_customer_accounts_overview(user))

    @action(methods=["get"], detail=False, url_path="virtual")
    def virtual_accounts(self, request):
        """当前用户所属商户的虚拟收款账户 (VA) 列表。

        资金流与信息流解耦: VA 看似独立银行账户，实则映射至伞形母账户，
        余额由母账户派生(账实分离)。
        """
        user = self._get_user(request)
        return Response(_customer_virtual_account_payload(user.default_merchant))

    @action(methods=["get"], detail=False, url_path="virtual/ledger")
    def virtual_ledger(self, request):
        """Current customer's VA ledger (collection credits and payout debits)."""
        user = self._get_user(request)
        merchant = user.default_merchant
        if not merchant:
            return Response({"items": [], "total": 0, "page": 1, "page_size": 50})

        from apps.account.models import VaLedgerEntry

        qs = (
            VaLedgerEntry.objects.filter(
                virtual_account__merchant=merchant,
                virtual_account__is_deleted=False,
                is_deleted=False,
            )
            .select_related("virtual_account", "order")
            .order_by("-created_at")
        )
        currency = (request.query_params.get("currency") or "").strip().upper()
        if currency:
            qs = qs.filter(virtual_account__currency=currency)
        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = min(max(int(request.query_params.get("page_size", 50)), 1), 100)
        except (TypeError, ValueError):
            page_size = 50
        total = qs.count()
        start = (page - 1) * page_size
        items = []
        for entry in qs[start:start + page_size]:
            items.append({
                "id": str(entry.id),
                "currency": (entry.virtual_account.currency or "").upper(),
                "entry_type": entry.entry_type,
                "amount": f"{entry.amount:.2f}",
                "balance_after": f"{entry.balance_after:.2f}",
                "order_no": entry.order.order_no if entry.order_id else "",
                "source_type": entry.source_type or "",
                "remark": entry.remark or "",
                "created_at": entry.created_at,
            })
        return Response({
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        })

    @action(methods=["get"], detail=False, url_path="currencies")
    def currencies(self, request):
        from apps.core.currencies import list_currencies

        self._get_user(request)
        return Response({"items": list_currencies()})

    @action(methods=["post"], detail=False, url_path="virtual/enable")
    def enable_virtual_account(self, request):
        from apps.core.currencies import is_supported_currency, normalize_currency
        from apps.merchant.services import ensure_merchant_currency_account

        user = self._get_user(request)
        merchant = user.default_merchant
        if not merchant:
            raise BusinessException(
                "MERCHANT_NOT_BOUND",
                "No customer entity is linked to this account. Contact operations.",
            )
        currency = normalize_currency(request.data.get("currency", ""))
        if not currency:
            raise BusinessException("PARAM_MISSING", "A required parameter is missing")
        if not is_supported_currency(currency):
            raise BusinessException("INVALID_CURRENCY", "The currency is not a supported ISO 4217 code")
        ensure_merchant_currency_account(merchant, currency)
        return Response(_customer_virtual_account_payload(merchant))

    @action(methods=["post"], detail=False, url_path="virtual/top-up")
    def virtual_top_up(self, request):
        user = self._get_user(request)
        payload = UserService().create_customer_virtual_top_up(
            user,
            currency=request.data.get("currency", ""),
            amount=request.data.get("amount"),
            remark=request.data.get("remark", ""),
        )
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(methods=["post"], detail=False, url_path="bind")
    def bind_account(self, request):
        user = self._get_user(request)
        bank_code = request.data.get("bank_code")
        bank_name = request.data.get("bank_name")
        account_holder = request.data.get("account_holder")
        account_number = request.data.get("account_number")
        bind_token = request.data.get("bind_token")
        currency = request.data.get("currency", "")
        merchant_no = request.data.get("merchant_no")
        if not merchant_no and user.default_merchant:
            merchant_no = user.default_merchant.merchant_no

        if not all([bank_code, bank_name, account_holder, account_number, merchant_no]):
            raise BusinessException("PARAM_MISSING", "A required parameter is missing")

        from apps.merchant.models import Merchant
        merchant = Merchant.objects.filter(merchant_no=merchant_no, is_deleted=False).first()
        if not merchant:
            raise BusinessException("MERCHANT_NOT_FOUND", "The customer does not exist")

        from apps.account.services import AccountService
        service = AccountService()
        account = service.bind_account(
            user_id=str(user.id),
            merchant_id=merchant,
            bank_code=bank_code,
            bank_name=bank_name,
            account_holder=account_holder,
            account_number=account_number,
            bind_token=bind_token or "",
        )

        from apps.core.currencies import is_supported_currency, normalize_currency
        from apps.merchant.services import ensure_merchant_currency_account

        ccy = normalize_currency(currency) if currency else ""
        if ccy:
            if not is_supported_currency(ccy):
                raise BusinessException("INVALID_CURRENCY", "The currency is not a supported ISO 4217 code")
            ensure_merchant_currency_account(merchant, ccy)
            from apps.account.models import VirtualAccount
            va = (
                VirtualAccount.objects.filter(merchant=merchant, currency=ccy, is_deleted=False)
                .order_by("-created_at")
                .first()
            )
            if va:
                va.bank_code = bank_code
                va.bank_name = bank_name
                va.account_holder = account_holder
                va.save(update_fields=["bank_code", "bank_name", "account_holder", "updated_at"])

        payload = _customer_accounts_overview(user)
        payload["bound"] = _serialize_bound_account(account)
        payload["currency"] = ccy
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(methods=["post"], detail=False, url_path="unbind")
    def unbind_account(self, request):
        user = self._get_user(request)
        account_id = request.data.get("account_id")
        if not account_id:
            raise BusinessException("PARAM_MISSING", "The account identifier is missing")
        from apps.account.models import UserAccount
        acc = UserAccount.objects.filter(
            id=account_id, user_id=str(user.id), is_deleted=False
        ).first()
        if not acc:
            raise BusinessException("ACCOUNT_NOT_FOUND", "The account does not exist")
        acc.status = UserAccount.BindStatus.REVOKED
        acc.save(update_fields=["status"])
        return Response({"message": "The account has been unlinked"})

    def _get_user(self, request) -> EndUser:
        if not request.user or not isinstance(request.user, EndUser):
            raise BusinessException("UNAUTHORIZED", "Authentication credentials are required", 401)
        return request.user


def _build_customer_order_timeline(order):
    from apps.payment.serializers import build_order_timeline
    return build_order_timeline(order)


class UserPaymentViewSet(viewsets.ViewSet):
    """用户端支付 — 支付历史查询、支付发起。"""
    authentication_classes = [JWTAuthentication]

    @action(methods=["get"], detail=False, url_path="history")
    def history(self, request):
        user = self._get_user(request)
        from apps.account.models import UserPaymentDetail
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))

        qs = UserPaymentDetail.objects.filter(
            user_id=str(user.id), is_deleted=False
        ).select_related("order", "account").order_by("-pay_time")

        total = qs.count()
        items = qs[(page - 1) * page_size : page * page_size]

        data = []
        for detail in items:
            order = detail.order
            data.append({
                "id": str(detail.id),
                "order_no": order.order_no if order else "",
                "merchant_name": order.merchant.merchant_name if order and order.merchant else "",
                "amount": str(detail.amount),
                "pay_method": detail.pay_method,
                "pay_time": detail.pay_time,
                "order_status": order.status if order else "",
            })

        seen = {row["order_no"] for row in data if row.get("order_no")}
        from apps.payment.models import PaymentOrder
        extra_orders = PaymentOrder.objects.filter(
            user_id=str(user.id), is_deleted=False
        ).select_related("merchant").order_by("-created_at")[:50]
        for extra in extra_orders:
            if extra.order_no in seen:
                continue
            data.append({
                "id": str(extra.id),
                "order_no": extra.order_no,
                "merchant_name": extra.merchant.merchant_name if extra.merchant else "",
                "amount": str(extra.amount),
                "pay_method": extra.pay_method,
                "pay_time": extra.pay_received_at or extra.created_at,
                "order_status": extra.status,
            })
            seen.add(extra.order_no)

        return Response({
            "total": max(total, len(data)),
            "page": page,
            "page_size": page_size,
            "items": data,
        })

    @action(methods=["get"], detail=False, url_path="order-detail")
    def order_detail(self, request):
        user = self._get_user(request)
        order_no = request.query_params.get("order_no")
        if not order_no:
            raise BusinessException("PARAM_MISSING", "The instruction number is missing")

        from apps.payment.models import PaymentOrder
        order = PaymentOrder.objects.filter(
            order_no=order_no, is_deleted=False
        ).select_related("merchant").first()

        if not order:
            raise BusinessException("ORDER_NOT_FOUND", "The payment instruction does not exist")

        # 检查是否是该用户的订单
        from apps.account.models import UserPaymentDetail
        owns_order = str(order.user_id or "") == str(user.id)
        has_payment_detail = UserPaymentDetail.objects.filter(
            user_id=str(user.id), order=order, is_deleted=False
        ).exists()
        if not owns_order and not has_payment_detail:
            raise BusinessException("PERMISSION_DENIED", "The authenticated principal is not authorised to view this instruction", 403)

        return Response({
            "order_no": order.order_no,
            "uin": order.unique_identification_no,
            "prn_code": order.prn_code,
            "merchant_name": order.merchant.merchant_name if order.merchant else "",
            "amount": str(order.amount),
            "fee": str(order.fee_amount),
            "fee_amount": str(order.fee_amount),
            "fee_currency": order.fee_currency,
            "sender_total": str(order.sender_total_amount),
            "settle_amount": str(order.settle_amount),
            "exchange_rate": str(order.exchange_rate) if order.exchange_rate else None,
            "currency": order.currency,
            "from_currency": order.from_currency,
            "to_currency": order.to_currency,
            "fee_bearing": order.fee_bearing or "",
            "beneficiary_name": order.beneficiary_name or "",
            "beneficiary_bank": order.beneficiary_bank or "",
            "beneficiary_account": order.beneficiary_account or "",
            "beneficiary_swift": order.beneficiary_swift or "",
            "beneficiary_address": order.beneficiary_address or "",
            "remittance_purpose": order.remittance_purpose or "",
            "pay_method": order.pay_method,
            "status": order.status,
            "product_name": order.get_pay_method_display(),
            "created_at": order.created_at,
            "reviewed_at": order.reviewed_at,
            "agent_review_status": order.agent_review_status,
            "agent_reviewed_by": order.agent_reviewed_by or "",
            "agent_reviewed_at": order.agent_reviewed_at,
            "agent_review_comment": order.agent_review_comment or "",
            "agent_payout_request_status": order.agent_payout_request_status,
            "agent_payout_requested_by": order.agent_payout_requested_by or "",
            "agent_payout_requested_at": order.agent_payout_requested_at,
            "expired_at": order.expire_at,
            "pay_received_at": order.pay_received_at,
            "settled_at": order.settled_at,
            "completed_at": order.completed_at,
            "closed_at": order.closed_at,
            "status_history": order.status_history or [],
            "timeline": _build_customer_order_timeline(order),
        })

    @action(methods=["post"], detail=False, url_path="refund-apply")
    def refund_apply(self, request):
        user = self._get_user(request)
        order_no = request.data.get("order_no")
        amount = request.data.get("refund_amount") or request.data.get("amount")
        reason = request.data.get("reason") or "Customer-initiated refund"
        from decimal import Decimal
        from apps.payment.models import PaymentOrder
        from apps.payment.services.refund import RefundService
        order = PaymentOrder.objects.filter(order_no=order_no, user_id=str(user.id), is_deleted=False).first()
        if not order:
            raise BusinessException("ORDER_NOT_FOUND", "The payment instruction does not exist")
        refund = RefundService().request_refund(
            payment_order=order,
            refund_amount=Decimal(str(amount)),
            reason=reason,
        )
        return Response({
            "refund_no": refund.refund_no,
            "status": refund.status,
            "refund_amount": str(refund.refund_amount),
        }, status=201)

    @action(methods=["get"], detail=False, url_path="refund-query")
    def refund_query(self, request):
        user = self._get_user(request)
        from apps.payment.models import RefundOrder
        qs = RefundOrder.objects.filter(
            payment_order__user_id=str(user.id), is_deleted=False
        ).select_related("payment_order")
        order_no = request.query_params.get("order_no")
        if order_no:
            qs = qs.filter(payment_order__order_no=order_no)
        return Response({
            "results": [{
                "refund_no": r.refund_no,
                "order_no": r.payment_order.order_no,
                "refund_amount": str(r.refund_amount),
                "status": r.status,
                "created_at": r.created_at,
            } for r in qs[:50]]
        })

    @action(methods=["post"], detail=False, url_path="manual-confirm")
    def manual_confirm(self, request):
        user = self._get_user(request)
        order_no = request.data.get("order_no")
        from apps.payment.services.payment import PaymentConfirmService
        order = PaymentConfirmService().manual_confirm_by_order_no(
            order_no, bank_txn_id=request.data.get("bank_txn_id"), user_id=str(user.id)
        )
        return Response({"status": order.status, "order_no": order.order_no})

    @action(methods=["post"], detail=False, url_path="apply")
    def apply_remittance(self, request):
        """客户使用其绑定商户的有效报价原子提交汇款。"""
        user = self._get_user(request)
        if user.onboarding_status != "approved":
            raise BusinessException("ONBOARDING_REQUIRED", "Onboarding review must be completed before a remittance may be initiated", 400)
        merchant = user.default_merchant
        if not merchant:
            raise BusinessException("MERCHANT_NOT_BOUND", "The account has not been bound to a customer; please contact operations", 400)
        from apps.payment.serializers import RemittanceSubmitSerializer, PaymentOrderSerializer
        from apps.payment.services.remittance_application import RemittanceApplicationService
        serializer = RemittanceSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order, created = RemittanceApplicationService().submit(
            merchant=merchant,
            payload=serializer.validated_data,
            idempotency_key=request.headers.get("Idempotency-Key", ""),
            user_id=str(user.id),
            actor_type="CUSTOMER",
        )
        return Response(
            PaymentOrderSerializer(order).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def _create_remittance_quote(self, request, data):
        user = self._get_user(request)
        if user.onboarding_status != "approved":
            raise BusinessException("ONBOARDING_REQUIRED", "Preliminary onboarding review must be completed first", 422)
        merchant = user.default_merchant
        if not merchant:
            raise BusinessException("MERCHANT_NOT_BOUND", "The account has not been bound to a customer", 422)
        from apps.payment.serializers import RemittanceQuoteRequestSerializer
        from apps.payment.services.remittance_quote import RemittanceQuoteService
        serializer = RemittanceQuoteRequestSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        quote = RemittanceQuoteService().create_quote(
            merchant=merchant,
            amount=serializer.validated_data["amount"],
            from_currency=serializer.validated_data["from_currency"],
            to_currency=serializer.validated_data["to_currency"],
            fee_bearing=serializer.validated_data["fee_bearing"],
            actor_type="CUSTOMER",
            user_id=str(user.id),
        )
        return RemittanceQuoteService.serialize(quote)

    @action(methods=["post"], detail=False, url_path="quote")
    def quote_remittance(self, request):
        return Response(
            self._create_remittance_quote(request, request.data),
            status=status.HTTP_201_CREATED,
        )

    @action(methods=["get"], detail=False, url_path="fee_preview")
    def fee_preview(self, request):
        """兼容旧客户门户；返回与 POST quote 相同的可提交报价。"""
        return Response(self._create_remittance_quote(request, request.query_params))

    @action(methods=["post"], detail=False, url_path="sanction-check")
    def sanction_check(self, request):
        self._get_user(request)
        beneficiary_name = (request.data.get("beneficiary_name") or "").strip()
        beneficiary_address = (request.data.get("beneficiary_address") or "").strip()
        from apps.compliance.services import scan_entity_lightweight, build_sanction_warning
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
            "warning_message": "" if result["is_clear"] else build_sanction_warning(
                result["name_hits"], result["address_hits"], result.get("country_hits", [])
            ),
        })

    @action(methods=["get"], detail=False, url_path="remittances")
    def remittances(self, request):
        user = self._get_user(request)
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        prn = (request.query_params.get("prn") or "").strip()
        from apps.payment.models import PaymentOrder
        qs = PaymentOrder.objects.filter(
            user_id=str(user.id), is_deleted=False
        ).order_by("-created_at")
        if prn:
            qs = qs.filter(prn_code__iexact=prn)
        total = qs.count()
        items = qs[(page - 1) * page_size : page * page_size]
        data = []
        for order in items:
            data.append({
                "order_no": order.order_no,
                "prn_code": order.prn_code,
                "amount": str(order.amount),
                "from_currency": order.from_currency,
                "to_currency": order.to_currency,
                "fee_amount": str(order.fee_amount or 0),
                "beneficiary_name": order.beneficiary_name,
                "status": order.status,
                "created_at": order.created_at,
            })
        return Response({"count": total, "results": data, "total": total, "items": data})

    def _get_user(self, request) -> EndUser:
        if not request.user or not isinstance(request.user, EndUser):
            raise BusinessException("UNAUTHORIZED", "Authentication credentials are required", 401)
        return request.user


class EndUserAdminViewSet(RequiresFeature, viewsets.ViewSet):
    """运营后台 — 终端用户（C端用户）管理。

    管理 EndUser 列表，支持搜索、绑定/解绑商户、启停用。
    """
    authentication_classes = [JWTAuthentication]
    feature_code = "feature:users"

    def list(self, request):
        return self.list_users(request)

    def retrieve(self, request, pk=None):
        user = EndUser.objects.filter(id=pk, is_deleted=False).select_related("default_merchant").first()
        if not user:
            raise BusinessException("USER_NOT_FOUND", "The user does not exist", 404)
        merchant = user.default_merchant
        return Response({
            "id": str(user.id),
            "username": user.username,
            "real_name": user.real_name,
            "email": user.email,
            "phone": user.phone,
            "is_active": user.is_active,
            "onboarding_status": user.onboarding_status,
            "merchant_name": merchant.merchant_name if merchant else "",
        })

    @action(methods=["get"], detail=False, url_path="list")
    def list_users(self, request):
        """终端用户列表 — 支持搜索和分页。

        Query params:
            search: 搜索用户名/邮箱/手机号
            page: 页码(默认1)
            page_size: 每页数量(默认20)
        """
        search = request.query_params.get("search", "")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))

        qs = EndUser.objects.filter(is_deleted=False).select_related("default_merchant")

        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
                | Q(real_name__icontains=search)
            )

        qs = qs.order_by("-created_at")
        total = qs.count()
        items = qs[(page - 1) * page_size : page * page_size]

        data = []
        for user in items:
            merchant = user.default_merchant
            data.append({
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "phone": user.phone or "",
                "nickname": user.nickname or "",
                "real_name": user.real_name or "",
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "onboarding_status": user.onboarding_status,
                "last_login_at": user.last_login_at,
                "created_at": user.created_at,
                "merchant_no": merchant.merchant_no if merchant else "",
                "merchant_name": merchant.merchant_name if merchant else "",
                "merchant_status": merchant.status if merchant else "",
            })

        return Response({
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": data,
        })

    @action(methods=["get"], detail=False, url_path="stats")
    def stats(self, request):
        """终端用户统计 — 总用户数/启用数/实名/绑定了商户的。"""
        qs = EndUser.objects.filter(is_deleted=False)
        total = qs.count()
        active = qs.filter(is_active=True).count()
        verified = qs.filter(is_verified=True).count()
        with_merchant = qs.exclude(default_merchant__isnull=True).count()
        return Response({
            "total": total,
            "active": active,
            "verified": verified,
            "with_merchant": with_merchant,
        })

    @action(methods=["post"], detail=True, url_path="bind-merchant")
    def bind_merchant(self, request, pk=None):
        """绑定终端用户的默认商户。"""
        user = EndUser.objects.filter(id=pk, is_deleted=False).first()
        if not user:
            raise BusinessException("USER_NOT_FOUND", "The user does not exist", 404)

        s = BindMerchantSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        from apps.merchant.models import Merchant
        merchant = Merchant.objects.filter(
            merchant_no=s.validated_data["merchant_no"], is_deleted=False
        ).first()
        if not merchant:
            raise BusinessException("MERCHANT_NOT_FOUND", "The customer does not exist", 404)

        user.default_merchant = merchant
        user.save(update_fields=["default_merchant"])
        return Response({
            "message": "The customer has been linked",
            "merchant_no": merchant.merchant_no,
            "merchant_name": merchant.merchant_name,
        })

    @action(methods=["post"], detail=True, url_path="unbind-merchant")
    def unbind_merchant(self, request, pk=None):
        """解绑终端用户的默认商户。"""
        user = EndUser.objects.filter(id=pk, is_deleted=False).first()
        if not user:
            raise BusinessException("USER_NOT_FOUND", "The user does not exist", 404)

        user.default_merchant = None
        user.save(update_fields=["default_merchant"])
        return Response({"message": "The account has been unlinked"})

    @action(methods=["post"], detail=True, url_path="toggle-status")
    def toggle_status(self, request, pk=None):
        """启用/停用终端用户。"""
        user = EndUser.objects.filter(id=pk, is_deleted=False).first()
        if not user:
            raise BusinessException("USER_NOT_FOUND", "The user does not exist", 404)

        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        return Response({
            "message": "The user has been {}".format("enabled" if user.is_active else "disabled"),
            "is_active": user.is_active,
        })

    @action(methods=["post"], detail=True, url_path="delete")
    def delete_user(self, request, pk=None):
        """软删除终端用户 — 标记 is_deleted=True 并停用。"""
        user = EndUser.objects.filter(id=pk, is_deleted=False).first()
        if not user:
            raise BusinessException("USER_NOT_FOUND", "The user does not exist", 404)

        user.is_deleted = True
        user.is_active = False
        user.save(update_fields=["is_deleted", "is_active"])
        return Response({"message": "The user has been deleted"})


class EndUserAccountAdminViewSet(RequiresFeature, viewsets.ViewSet):
    """运营后台 — 终端用户银行账户列表。"""
    authentication_classes = [JWTAuthentication]
    feature_code = "feature:users"

    def list(self, request):
        from apps.account.models import UserAccount
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        qs = UserAccount.objects.filter(is_deleted=False).select_related("merchant").order_by("-created_at")
        total = qs.count()
        items = qs[(page - 1) * page_size : page * page_size]
        data = []
        for acc in items:
            data.append({
                "id": str(acc.id),
                "account_no": ("****" + acc.account_number[-4:]) if acc.account_number and len(acc.account_number) >= 4 else (acc.account_number or ""),
                "phone": "",
                "bank_code": acc.bank_code,
                "bank_name": acc.bank_name,
                "account_holder": acc.account_holder,
                "status": acc.status,
                "merchant_name": acc.merchant.merchant_name if acc.merchant else "",
                "user_id": acc.user_id,
                "bind_at": acc.bind_at,
            })
        return Response({"count": total, "results": data})


class EndUserPaymentAdminViewSet(RequiresFeature, viewsets.ViewSet):
    """运营后台 — 终端用户支付明细列表。"""
    authentication_classes = [JWTAuthentication]
    feature_code = "feature:users"

    def list(self, request):
        from apps.account.models import UserPaymentDetail
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        qs = UserPaymentDetail.objects.filter(is_deleted=False).select_related(
            "order", "order__merchant"
        ).order_by("-pay_time")
        total = qs.count()
        items = qs[(page - 1) * page_size : page * page_size]
        data = []
        for detail in items:
            order = detail.order
            data.append({
                "id": str(detail.id),
                "order_no": order.order_no if order else "",
                "amount": str(detail.amount),
                "currency": order.currency if order else "CNY",
                "pay_method": detail.pay_method,
                "pay_time": detail.pay_time,
                "order_status": order.status if order else "",
                "merchant_name": order.merchant.merchant_name if order and order.merchant else "",
            })
        return Response({"count": total, "results": data})
