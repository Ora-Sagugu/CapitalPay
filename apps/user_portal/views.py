"""用户端 API 视图 — 注册、登录、账户绑定、交易查询、支付发起、首次登录资料。"""
from django.db.models import Q
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import BusinessException
from apps.rbac.authentication import JWTAuthentication
from .models import EndUser
from .serializers import (
    RegisterSerializer, RegisterByEmailSerializer,
    LoginByPasswordSerializer, LoginByEmailSerializer, LoginBySmsSerializer,
    SmsCodeSerializer, ResetPasswordSerializer, RefreshTokenSerializer,
    ProfileUpdateSerializer, IdentityVerifySerializer,
    OnboardingSubmitSerializer, OnboardingReviewSerializer,
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
        return Response({"message": "资料更新成功"})

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
        return Response({"message": "实名认证成功"})

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
        return Response({"message": "密码重置成功"})

    def _get_user(self, request) -> EndUser:
        if not request.user or not isinstance(request.user, EndUser):
            raise BusinessException("UNAUTHORIZED", "请先登录", 401)
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
        return Response({
            "onboarding_status": user.onboarding_status,
            "submitted_at": user.onboarding_submitted_at,
            "reviewed_at": user.onboarding_reviewed_at,
            "reviewer": user.onboarding_reviewer,
            "remark": user.onboarding_remark,
            "data": onboarding,
        })

    def _get_user(self, request) -> EndUser:
        if not request.user or not isinstance(request.user, EndUser):
            raise BusinessException("UNAUTHORIZED", "请先登录", 401)
        return request.user


class UserOnboardingAdminViewSet(viewsets.ViewSet):
    """用户资料审核 — 运营后台使用。"""
    authentication_classes = [JWTAuthentication]
    service = UserService()

    def list(self, request):
        """GET /api/v1/admin/onboarding/ — 分页列表。"""
        return self.list_onboarding(request)

    @action(methods=["get"], detail=False, url_path="list")
    def list_onboarding(self, request):
        status_filter = request.query_params.get("status")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        qs = EndUser.objects.filter(is_deleted=False).exclude(onboarding_status="none")
        if status_filter:
            qs = qs.filter(onboarding_status=status_filter)
        qs = qs.order_by("-onboarding_submitted_at")
        total = qs.count()
        items = qs[(page - 1) * page_size : page * page_size]
        data = []
        for user in items:
            data.append({
                "id": str(user.id),
                "username": user.username,
                "name": user.real_name or user.nickname or user.username,
                "email": user.email,
                "phone": user.phone or "",
                "status": user.onboarding_status,
                "onboarding_status": user.onboarding_status,
                "submitted_at": user.onboarding_submitted_at,
                "reviewed_at": user.onboarding_reviewed_at,
                "reviewer": user.onboarding_reviewer,
                "remark": user.onboarding_remark,
            })
        return Response({
            "count": total,
            "results": data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": data,
        })

    @action(methods=["post"], detail=True, url_path="review")
    def review(self, request, pk=None):
        user = EndUser.objects.filter(id=pk, is_deleted=False).first()
        if not user:
            raise BusinessException("USER_NOT_FOUND", "用户不存在", 404)

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
            raise BusinessException("USER_NOT_FOUND", "用户不存在", 404)
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        return Response({
            "message": "用户已{}".format("启用" if user.is_active else "停用"),
            "is_active": user.is_active,
        })

    @action(methods=["get"], detail=True, url_path="detail")
    def onboarding_detail(self, request, pk=None):
        user = EndUser.objects.filter(id=pk, is_deleted=False).first()
        if not user:
            raise BusinessException("USER_NOT_FOUND", "用户不存在", 404)

        onboarding = self.service.get_onboarding(user)
        return Response({
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "onboarding_status": user.onboarding_status,
            "submitted_at": user.onboarding_submitted_at,
            "reviewed_at": user.onboarding_reviewed_at,
            "reviewer": user.onboarding_reviewer,
            "remark": user.onboarding_remark,
            "data": onboarding,
        })


class UserAccountViewSet(viewsets.ViewSet):
    """用户账户管理 — 银行账户绑定、解绑、查询。"""
    authentication_classes = [JWTAuthentication]

    @action(methods=["get"], detail=False, url_path="list")
    def list_accounts(self, request):
        user = self._get_user(request)
        from apps.account.models import UserAccount
        accounts = UserAccount.objects.filter(
            user_id=str(user.id), is_deleted=False
        ).select_related("merchant").order_by("-created_at")
        data = []
        for acc in accounts:
            data.append({
                "id": str(acc.id),
                "bank_code": acc.bank_code,
                "bank_name": acc.bank_name,
                "account_holder": acc.account_holder,
                "status": acc.status,
                "merchant_name": acc.merchant.merchant_name if acc.merchant else "",
                "merchant_no": acc.merchant.merchant_no if acc.merchant else "",
                "bind_at": acc.bind_at,
                "expire_at": acc.expire_at,
            })
        return Response(data)

    @action(methods=["get"], detail=False, url_path="virtual")
    def virtual_accounts(self, request):
        """当前用户所属商户的虚拟收款账户 (VA) 列表。

        资金流与信息流解耦: VA 看似独立银行账户，实则映射至伞形母账户，
        余额由母账户派生(账实分离)。
        """
        user = self._get_user(request)
        merchant = user.default_merchant
        if not merchant:
            return Response({
                "merchant_name": "",
                "merchant_no": "",
                "virtual_accounts": [],
            })
        from apps.account.models import VirtualAccount
        vas = VirtualAccount.objects.filter(
            merchant=merchant, is_deleted=False
        ).select_related("master_account").order_by("-created_at")
        data = []
        for va in vas:
            master = va.master_account
            data.append({
                "id": str(va.id),
                "va_number": va.va_number,
                "va_type": va.va_type,
                "label": va.label,
                "reference": va.reference,
                "bank_code": va.bank_code,
                "bank_name": va.bank_name,
                "account_holder": va.account_holder,
                "routing_code": va.routing_code,
                "clearing_network": va.clearing_network,
                "country": va.country,
                "currency": va.currency,
                "balance": str(master.balance) if master else "0",
                "status": va.status,
                "opened_at": va.opened_at,
            })
        return Response({
            "merchant_name": merchant.merchant_name,
            "merchant_no": merchant.merchant_no,
            "virtual_accounts": data,
        })

    @action(methods=["post"], detail=False, url_path="bind")
    def bind_account(self, request):
        user = self._get_user(request)
        bank_code = request.data.get("bank_code")
        bank_name = request.data.get("bank_name")
        account_holder = request.data.get("account_holder")
        account_number = request.data.get("account_number")
        bind_token = request.data.get("bind_token")
        merchant_no = request.data.get("merchant_no")

        if not all([bank_code, bank_name, account_holder, account_number, merchant_no]):
            raise BusinessException("PARAM_MISSING", "缺少必填参数")

        from apps.merchant.models import Merchant
        merchant = Merchant.objects.filter(merchant_no=merchant_no, is_deleted=False).first()
        if not merchant:
            raise BusinessException("MERCHANT_NOT_FOUND", "商户不存在")

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
        return Response({
            "id": str(account.id),
            "bank_name": account.bank_name,
            "status": account.status,
        }, status=status.HTTP_201_CREATED)

    @action(methods=["post"], detail=False, url_path="unbind")
    def unbind_account(self, request):
        user = self._get_user(request)
        account_id = request.data.get("account_id")
        if not account_id:
            raise BusinessException("PARAM_MISSING", "缺少账户ID")
        from apps.account.models import UserAccount
        acc = UserAccount.objects.filter(
            id=account_id, user_id=str(user.id), is_deleted=False
        ).first()
        if not acc:
            raise BusinessException("ACCOUNT_NOT_FOUND", "账户不存在")
        acc.status = UserAccount.BindStatus.REVOKED
        acc.save(update_fields=["status"])
        return Response({"message": "解绑成功"})

    def _get_user(self, request) -> EndUser:
        if not request.user or not isinstance(request.user, EndUser):
            raise BusinessException("UNAUTHORIZED", "请先登录", 401)
        return request.user


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

        return Response({
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": data,
        })

    @action(methods=["get"], detail=False, url_path="order-detail")
    def order_detail(self, request):
        user = self._get_user(request)
        order_no = request.query_params.get("order_no")
        if not order_no:
            raise BusinessException("PARAM_MISSING", "缺少订单号")

        from apps.payment.models import PaymentOrder
        order = PaymentOrder.objects.filter(
            order_no=order_no, is_deleted=False
        ).select_related("merchant").first()

        if not order:
            raise BusinessException("ORDER_NOT_FOUND", "订单不存在")

        # 检查是否是该用户的订单
        from apps.account.models import UserPaymentDetail
        detail = UserPaymentDetail.objects.filter(
            user_id=str(user.id), order=order, is_deleted=False
        ).first()
        if not detail:
            raise BusinessException("PERMISSION_DENIED", "无权查看此订单", 403)

        return Response({
            "order_no": order.order_no,
            "uin": order.uin,
            "merchant_name": order.merchant.merchant_name if order.merchant else "",
            "amount": str(order.amount),
            "fee": str(order.fee),
            "currency": order.currency,
            "pay_method": order.pay_method,
            "status": order.status,
            "product_name": order.product_name,
            "created_at": order.created_at,
            "expired_at": order.expired_at,
            "pay_received_at": order.pay_received_at,
            "settled_at": order.settled_at,
        })

    def _get_user(self, request) -> EndUser:
        if not request.user or not isinstance(request.user, EndUser):
            raise BusinessException("UNAUTHORIZED", "请先登录", 401)
        return request.user


class EndUserAdminViewSet(viewsets.ViewSet):
    """运营后台 — 终端用户（C端用户）管理。

    管理 EndUser 列表，支持搜索、绑定/解绑商户、启停用。
    """
    authentication_classes = [JWTAuthentication]

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
            raise BusinessException("USER_NOT_FOUND", "用户不存在", 404)

        s = BindMerchantSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        from apps.merchant.models import Merchant
        merchant = Merchant.objects.filter(
            merchant_no=s.validated_data["merchant_no"], is_deleted=False
        ).first()
        if not merchant:
            raise BusinessException("MERCHANT_NOT_FOUND", "商户不存在", 404)

        user.default_merchant = merchant
        user.save(update_fields=["default_merchant"])
        return Response({
            "message": "绑定成功",
            "merchant_no": merchant.merchant_no,
            "merchant_name": merchant.merchant_name,
        })

    @action(methods=["post"], detail=True, url_path="unbind-merchant")
    def unbind_merchant(self, request, pk=None):
        """解绑终端用户的默认商户。"""
        user = EndUser.objects.filter(id=pk, is_deleted=False).first()
        if not user:
            raise BusinessException("USER_NOT_FOUND", "用户不存在", 404)

        user.default_merchant = None
        user.save(update_fields=["default_merchant"])
        return Response({"message": "解绑成功"})

    @action(methods=["post"], detail=True, url_path="toggle-status")
    def toggle_status(self, request, pk=None):
        """启用/停用终端用户。"""
        user = EndUser.objects.filter(id=pk, is_deleted=False).first()
        if not user:
            raise BusinessException("USER_NOT_FOUND", "用户不存在", 404)

        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        return Response({
            "message": "用户已{}".format("启用" if user.is_active else "停用"),
            "is_active": user.is_active,
        })

    @action(methods=["post"], detail=True, url_path="delete")
    def delete_user(self, request, pk=None):
        """软删除终端用户 — 标记 is_deleted=True 并停用。"""
        user = EndUser.objects.filter(id=pk, is_deleted=False).first()
        if not user:
            raise BusinessException("USER_NOT_FOUND", "用户不存在", 404)

        user.is_deleted = True
        user.is_active = False
        user.save(update_fields=["is_deleted", "is_active"])
        return Response({"message": "用户已删除"})


class EndUserAccountAdminViewSet(viewsets.ViewSet):
    """运营后台 — 终端用户银行账户列表。"""
    authentication_classes = [JWTAuthentication]

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


class EndUserPaymentAdminViewSet(viewsets.ViewSet):
    """运营后台 — 终端用户支付明细列表。"""
    authentication_classes = [JWTAuthentication]

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
