"""商户管理 — 业务服务层。"""
from __future__ import annotations
from decimal import Decimal
from datetime import date
import datetime
import uuid
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.exceptions import BusinessException, ErrorCode
from apps.core.utils import encrypt_field, decrypt_field
from apps.account.models import NostroAccount
from .models import (
    Merchant,
    MerchantKYC,
    MerchantFee,
    MerchantSettlementAccount,
    MerchantPaymentProduct,
    MerchantStatusEvent,
)
from .serializers import _linked_username


def ensure_merchant_account(merchant: Merchant) -> NostroAccount | None:
    """确保商户(客户)拥有至少一个 Nostro 账户。

    若商户当前没有任何未删除的账户，则为其创建一个默认收款账户。
    返回新建的账户；若已存在则不做任何操作并返回 None。
    """
    if merchant.nostro_accounts.filter(is_deleted=False).exists():
        return None
    account_no = f"N{datetime.date.today().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
    return NostroAccount.objects.create(
        merchant=merchant,
        account_no=account_no,
        bank_code="NSTR",
        bank_name="CapitalPay Nostro",
        account_number=f"ACCT-{merchant.merchant_no}",
        account_type=NostroAccount.AccountType.COLLECTION,
        currency="CNY",
        balance=Decimal("0"),
    )


def ensure_merchant_virtual_account(merchant: Merchant):
    """确保商户(客户)拥有至少一个虚拟账户 (Virtual Account)。

    若商户当前没有任何未删除的虚拟账户，则为其默认收款母账户创建一个 VAV。
    返回新建的 VA；若已存在则不做任何操作并返回 None。
    """
    from apps.account.models import VirtualAccount

    if merchant.virtual_accounts.filter(is_deleted=False).exists():
        return None

    # 确保有一个母账户(默认收款账户)
    master = merchant.nostro_accounts.filter(
        is_deleted=False, account_type=NostroAccount.AccountType.COLLECTION
    ).first()
    if not master:
        master = ensure_merchant_account(merchant)
    if not master:
        return None

    va_number = f"VAV{datetime.date.today().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"
    return VirtualAccount.objects.create(
        master_account=master,
        merchant=merchant,
        va_number=va_number,
        va_type=VirtualAccount.VaType.VAV,
        label=f"{merchant.merchant_name} Collection VA",
        reference=merchant.merchant_no,
        bank_code=master.bank_code,
        bank_name=master.bank_name,
        account_holder=merchant.merchant_name,
        routing_code="",
        clearing_network="",
        country="CN",
        currency=master.currency or "CNY",
        status=VirtualAccount.VaStatus.ACTIVE,
        opened_at=timezone.now(),
    )


MULTI_CURRENCIES = ("CNY", "USD", "EUR", "HKD")


def ensure_merchant_currency_account(merchant: Merchant, currency: str):
    """为指定 ISO 币种确保 COLLECTION 母户与对应 VAV 存在。重复调用幂等。"""
    from apps.account.models import VirtualAccount
    from apps.core.currencies import is_supported_currency, normalize_currency

    ccy = normalize_currency(currency)
    if not is_supported_currency(ccy):
        raise BusinessException("INVALID_CURRENCY", "The currency is not a supported ISO 4217 code")

    master = merchant.nostro_accounts.filter(is_deleted=False, currency=ccy).first()
    created_master = None
    if not master:
        account_no = f"N{datetime.date.today().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
        master = NostroAccount.objects.create(
            merchant=merchant,
            account_no=account_no,
            bank_code="NSTR",
            bank_name="CapitalPay Nostro",
            account_number=f"ACCT-{merchant.merchant_no}-{ccy}",
            account_type=NostroAccount.AccountType.COLLECTION,
            currency=ccy,
            balance=Decimal("0"),
        )
        created_master = master
    if not merchant.virtual_accounts.filter(is_deleted=False, currency=ccy).exists():
        va_number = f"VAV{datetime.date.today().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"
        VirtualAccount.objects.create(
            master_account=master,
            merchant=merchant,
            va_number=va_number,
            va_type=VirtualAccount.VaType.VAV,
            label=f"{merchant.merchant_name} {ccy} VA",
            reference=f"{merchant.merchant_no}-{ccy}",
            bank_code=master.bank_code,
            bank_name=master.bank_name,
            account_holder=merchant.merchant_name,
            routing_code="",
            clearing_network="",
            country="CN",
            currency=ccy,
            status=VirtualAccount.VaStatus.ACTIVE,
            opened_at=timezone.now(),
        )
    return created_master


def ensure_merchant_multi_currency_accounts(merchant: Merchant):
    """Seed / 补齐命令使用：按手册开通 CNY/USD/EUR/HKD 收款账户与对应 VA。"""
    ensure_merchant_account(merchant)
    created = []
    for ccy in MULTI_CURRENCIES:
        created_master = ensure_merchant_currency_account(merchant, ccy)
        if created_master:
            created.append(created_master)
    return created


class MerchantLifecycleService:
    """商户状态机的唯一写入口。"""

    ALLOWED_TRANSITIONS = {
        Merchant.Status.PENDING: {Merchant.Status.ACTIVE, Merchant.Status.CLOSED},
        Merchant.Status.ACTIVE: {Merchant.Status.SUSPENDED, Merchant.Status.CLOSED},
        Merchant.Status.SUSPENDED: {Merchant.Status.ACTIVE, Merchant.Status.CLOSED},
        Merchant.Status.CLOSED: set(),
    }

    @staticmethod
    def activation_blockers(merchant: Merchant) -> list[dict]:
        blockers = []
        today = timezone.localdate()
        try:
            kyc_status = merchant.kyc.kyc_status
        except MerchantKYC.DoesNotExist:
            kyc_status = ""
        if kyc_status != MerchantKYC.Status.APPROVED:
            blockers.append({"code": "KYC_NOT_APPROVED", "message": "Customer due diligence (KYC) has not been approved"})
        if not merchant.license_expiry_date:
            blockers.append({"code": "LICENSE_REQUIRED", "message": "The customer's business licence expiry date has not been provided"})
        elif merchant.license_expiry_date < today:
            blockers.append({
                "code": "LICENSE_EXPIRED",
                "message": f"The customer's business licence expired on {merchant.license_expiry_date}",
            })
        if merchant.risk_level == "BLOCKED":
            blockers.append({"code": "MERCHANT_RISK_BLOCKED", "message": "The customer's risk classification prohibits further transactions"})
        if merchant.sanction_status != "UN":
            blockers.append({"code": "MERCHANT_SANCTIONED", "message": "The customer is subject to sanctions restrictions"})
        product = MerchantPaymentProduct.objects.filter(
            merchant=merchant,
            product_type=MerchantFee.ProductType.WIRE_TRANSFER,
            is_enabled=True,
            is_deleted=False,
        ).first()
        if not product:
            blockers.append({"code": "PRODUCT_NOT_ENABLED", "message": "The wire-transfer remittance product has not been enabled for this customer"})
        # Settlement banks may be configured later; remittance eligibility still
        # checks for a default settlement account separately.
        return blockers

    @transaction.atomic
    def transition(
        self,
        merchant: Merchant,
        to_status: str,
        *,
        reason_code: str,
        comment: str = "",
        actor: str = "",
        source: str = "API",
    ) -> Merchant:
        locked = Merchant.objects.select_for_update().get(pk=merchant.pk)
        from_status = locked.status
        if from_status == to_status:
            return locked
        if to_status not in self.ALLOWED_TRANSITIONS.get(from_status, set()):
            raise BusinessException(
                "MERCHANT_STATUS_TRANSITION_INVALID",
                f"The customer status may not be changed from {from_status} to {to_status}",
                409,
            )
        if to_status == Merchant.Status.ACTIVE:
            blockers = self.activation_blockers(locked)
            if blockers:
                first = blockers[0]
                raise BusinessException(first["code"], first["message"], 422)

        now = timezone.now()
        locked.status = to_status
        locked.status_reason_code = reason_code
        locked.status_changed_at = now
        locked._lifecycle_status_write = True
        locked.save(update_fields=[
            "status", "status_reason_code", "status_changed_at", "updated_at",
        ])
        MerchantStatusEvent.objects.create(
            merchant=locked,
            from_status=from_status,
            to_status=to_status,
            reason_code=reason_code,
            comment=comment,
            actor=actor,
            source=source,
        )
        merchant.status = locked.status
        merchant.status_reason_code = locked.status_reason_code
        merchant.status_changed_at = locked.status_changed_at
        return locked

    def activate(self, merchant: Merchant, **kwargs) -> Merchant:
        return self.transition(merchant, Merchant.Status.ACTIVE, **kwargs)

    def suspend(self, merchant: Merchant, **kwargs) -> Merchant:
        return self.transition(merchant, Merchant.Status.SUSPENDED, **kwargs)

    def close(self, merchant: Merchant, **kwargs) -> Merchant:
        return self.transition(merchant, Merchant.Status.CLOSED, **kwargs)


class MerchantService:
    """商户管理服务。"""

    # ── 商户信息查询 ────────────────────────────────────────

    def get_by_merchant_no(self, merchant_no: str) -> Merchant:
        """按商户编号查询。"""
        try:
            return Merchant.objects.get(merchant_no=merchant_no, is_deleted=False)
        except Merchant.DoesNotExist:
            raise BusinessException(ErrorCode.MERCHANT_NOT_FOUND)

    def get_by_api_key(self, api_key: str) -> Merchant:
        """按 API Key 查询（用于鉴权）。"""
        try:
            return Merchant.objects.get(api_key=api_key, is_deleted=False)
        except Merchant.DoesNotExist:
            raise BusinessException(ErrorCode.MERCHANT_NOT_FOUND)

    def list_active_merchants(self):
        """列出所有活跃商户。"""
        return Merchant.objects.filter(status=Merchant.Status.ACTIVE, is_deleted=False)

    # ── KYC 管理 ────────────────────────────────────────────

    @transaction.atomic
    def set_kyc(self, merchant: Merchant, kyc_data: dict) -> MerchantKYC:
        """设置/更新商户 KYC 信息 — 敏感字段自动加密。"""
        existing = MerchantKYC.objects.filter(merchant=merchant).first()
        kyc, _ = MerchantKYC.objects.update_or_create(
            merchant=merchant,
            defaults={
                "legal_person": kyc_data["legal_person"],
                "id_number": encrypt_field(kyc_data["id_number"]),
                "business_license": encrypt_field(kyc_data.get("business_license", "")),
                "business_scope": kyc_data.get("business_scope", ""),
                "registered_capital": kyc_data.get("registered_capital"),
                "established_date": kyc_data.get("established_date"),
                "registered_address": kyc_data.get("registered_address", ""),
                "kyc_status": MerchantKYC.Status.PENDING,
                "reviewed_at": None,
                "remark": "",
            },
        )
        if existing and existing.kyc_status == MerchantKYC.Status.APPROVED:
            merchant.refresh_from_db()
            if merchant.status == Merchant.Status.ACTIVE:
                MerchantLifecycleService().suspend(
                    merchant,
                    reason_code="KYC_UPDATED",
                    comment="关键 KYC 资料已修改，等待重新审核",
                    actor="system",
                    source="KYC",
                )
        return kyc

    @transaction.atomic
    def review_kyc(
        self,
        merchant: Merchant,
        review_data: dict,
        *,
        actor: str = "",
    ) -> MerchantKYC:
        """原子完成 KYC 复核、汇款产品/费率配置与商户激活。"""
        merchant = Merchant.objects.select_for_update().get(pk=merchant.pk)
        try:
            kyc = MerchantKYC.objects.select_for_update().get(merchant=merchant)
        except MerchantKYC.DoesNotExist:
            raise BusinessException("KYC_NOT_SUBMITTED", "The customer has not submitted customer due diligence (KYC) information", 422)

        if kyc.kyc_status != MerchantKYC.Status.PENDING:
            raise BusinessException(
                "KYC_STATUS_INVALID",
                f"Customer due diligence (KYC) is currently {kyc.kyc_status} and may not be reviewed again",
                409,
            )

        now = timezone.now()
        if review_data["action"] == "reject":
            kyc.kyc_status = MerchantKYC.Status.REJECTED
            kyc.remark = review_data["reason"].strip()
            kyc.reviewed_at = now
            kyc.save(update_fields=["kyc_status", "remark", "reviewed_at", "updated_at"])
            if merchant.status == Merchant.Status.ACTIVE:
                MerchantLifecycleService().suspend(
                    merchant,
                    reason_code="KYC_REJECTED",
                    comment=kyc.remark,
                    actor=actor,
                    source="KYC_REVIEW",
                )
            return kyc

        if not merchant.license_expiry_date:
            raise BusinessException("LICENSE_REQUIRED", "The business licence expiry date must be provided first", 422)
        if merchant.license_expiry_date < timezone.localdate():
            raise BusinessException(
                "LICENSE_EXPIRED",
                f"The customer's business licence expired on {merchant.license_expiry_date}",
                422,
            )

        merchant.risk_level = review_data.get("risk_level", "MEDIUM")
        merchant.max_single_amount = review_data.get("max_single_amount")
        merchant.daily_limit = review_data.get("daily_limit")
        merchant.daily_count = review_data.get("daily_count")
        merchant.save(update_fields=[
            "risk_level", "max_single_amount", "daily_limit", "daily_count", "updated_at",
        ])

        MerchantPaymentProduct.objects.update_or_create(
            merchant=merchant,
            product_type=MerchantFee.ProductType.WIRE_TRANSFER,
            defaults={
                "is_enabled": True,
                "max_single_amount": review_data.get("max_single_amount"),
                "daily_limit": review_data.get("daily_limit"),
                "is_deleted": False,
            },
        )

        current_fee = self.get_current_fee(
            merchant, MerchantFee.ProductType.WIRE_TRANSFER
        )
        fee_values = {
            "fee_model": review_data.get("fee_model", MerchantFee.FeeModel.PERCENTAGE),
            "fixed_fee": review_data.get("fixed_fee", Decimal("0")),
            "fee_rate": review_data.get("fee_rate", Decimal("0")),
            "min_fee": review_data.get("min_fee", Decimal("0")),
            "max_fee": review_data.get("max_fee"),
            "effective_from": timezone.localdate(),
            "effective_to": None,
            "is_deleted": False,
        }
        if current_fee:
            for field, value in fee_values.items():
                setattr(current_fee, field, value)
            current_fee.save(update_fields=[*fee_values.keys(), "updated_at"])
        else:
            MerchantFee.objects.create(
                merchant=merchant,
                product_type=MerchantFee.ProductType.WIRE_TRANSFER,
                **fee_values,
            )

        kyc.kyc_status = MerchantKYC.Status.APPROVED
        kyc.remark = review_data.get("reason", "").strip()
        kyc.reviewed_at = now
        kyc.save(update_fields=["kyc_status", "remark", "reviewed_at", "updated_at"])

        activated = MerchantLifecycleService().activate(
            merchant,
            reason_code="KYC_APPROVED",
            comment="KYC、汇款产品与费率审核通过",
            actor=actor,
            source="KYC_REVIEW",
        )
        merchant.status = activated.status
        return kyc

    def get_kyc(self, merchant: Merchant) -> dict:
        """获取商户 KYC — 敏感字段解密。"""
        try:
            kyc = merchant.kyc
            payload = {
                "username": _linked_username(merchant),
                "merchant_no": merchant.merchant_no,
                "kyc_status": kyc.kyc_status,
                "legal_person": kyc.legal_person,
                "id_number": decrypt_field(kyc.id_number) or kyc.id_number_plain,
                "business_license": decrypt_field(kyc.business_license),
                "business_scope": kyc.business_scope,
                "registered_capital": str(kyc.registered_capital) if kyc.registered_capital else None,
                "established_date": str(kyc.established_date) if kyc.established_date else None,
                "registered_address": kyc.registered_address,
            }
            return payload
        except MerchantKYC.DoesNotExist:
            return {"username": _linked_username(merchant), "merchant_no": merchant.merchant_no}

    # ── 手续费管理 ──────────────────────────────────────────

    @transaction.atomic
    def set_fee(self, merchant: Merchant, fee_data: dict) -> MerchantFee:
        """设置商户手续费。"""
        fee = MerchantFee.objects.create(
            merchant=merchant,
            product_type=fee_data["product_type"],
            fee_model=fee_data["fee_model"],
            fixed_fee=fee_data.get("fixed_fee", Decimal("0")),
            fee_rate=fee_data.get("fee_rate", Decimal("0")),
            min_fee=fee_data.get("min_fee", Decimal("0")),
            max_fee=fee_data.get("max_fee"),
            effective_from=fee_data.get("effective_from", date.today()),
            effective_to=fee_data.get("effective_to"),
        )
        return fee

    def get_current_fee(self, merchant: Merchant, product_type: str) -> MerchantFee | None:
        """获取商户当前生效的手续费配置。"""
        today = date.today()
        return MerchantFee.objects.filter(
            merchant=merchant,
            product_type=product_type,
            effective_from__lte=today,
            is_deleted=False,
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=today)
        ).order_by("-effective_from").first()

    def calculate_fee(self, merchant: Merchant, amount: Decimal, product_type: str) -> dict:
        """计算手续费。优先商户产品费率，否则回落手续费模型 / 商户默认费率。

        Returns:
            {"fee_amount": Decimal, "settle_amount": Decimal, "fee_model": str}
        """
        amount = Decimal(str(amount))
        fee_config = self.get_current_fee(merchant, product_type)
        if fee_config:
            if fee_config.fee_model == MerchantFee.FeeModel.FIXED:
                fee_amount = Decimal(str(fee_config.fixed_fee or 0))
            elif fee_config.fee_model == MerchantFee.FeeModel.PERCENTAGE:
                fee_amount = amount * Decimal(str(fee_config.fee_rate or 0))
                fee_amount = max(fee_amount, Decimal(str(fee_config.min_fee or 0)))
                if fee_config.max_fee:
                    fee_amount = min(fee_amount, Decimal(str(fee_config.max_fee)))
            else:
                # TIERED：无阶梯配置时按比例计算
                fee_amount = amount * Decimal(str(fee_config.fee_rate or 0))
                if fee_config.fixed_fee:
                    fee_amount += Decimal(str(fee_config.fixed_fee))
                fee_amount = max(fee_amount, Decimal(str(fee_config.min_fee or 0)))
                if fee_config.max_fee:
                    fee_amount = min(fee_amount, Decimal(str(fee_config.max_fee)))
            fee_model = fee_config.fee_model
        else:
            from apps.param.models import FeeModel
            from apps.param.services import compute_fee_from_model

            model = FeeModel.objects.filter(status="active").order_by("model_code").first()
            if model:
                fee_amount = compute_fee_from_model(model, amount)
                fee_model = model.fee_type.upper()
            elif merchant.fee_rate or merchant.fixed_fee:
                fee_amount = amount * (merchant.fee_rate or Decimal("0")) + (merchant.fixed_fee or Decimal("0"))
                fee_model = "MERCHANT_DEFAULT"
            else:
                raise BusinessException(ErrorCode.FEE_NOT_CONFIGURED)

        fee_amount = Decimal(str(fee_amount)).quantize(Decimal("0.01"))
        settle_amount = amount - fee_amount
        return {
            "fee_amount": fee_amount,
            "settle_amount": settle_amount,
            "fee_model": fee_model,
        }

    # ── 结算账户管理 ────────────────────────────────────────

    @transaction.atomic
    def set_settlement_account(self, merchant: Merchant, account_data: dict) -> MerchantSettlementAccount:
        """设置商户结算账户。"""
        account = MerchantSettlementAccount.objects.create(
            merchant=merchant,
            bank_name=account_data["bank_name"],
            bank_branch=account_data.get("bank_branch", ""),
            account_name=account_data["account_name"],
            account_number=encrypt_field(account_data["account_number"]),
            account_type=account_data.get("account_type", "CORPORATE"),
            is_default=account_data.get("is_default", False),
        )
        return account

    def get_default_settlement_account(self, merchant: Merchant) -> MerchantSettlementAccount | None:
        """获取商户默认结算账户。"""
        return MerchantSettlementAccount.objects.filter(
            merchant=merchant, is_default=True, is_deleted=False
        ).first()

    # ── 支付产品管理 ────────────────────────────────────────

    @transaction.atomic
    def set_payment_product(self, merchant: Merchant, product_data: dict) -> MerchantPaymentProduct:
        """设置商户支付产品。"""
        product, _ = MerchantPaymentProduct.objects.update_or_create(
            merchant=merchant,
            product_type=product_data["product_type"],
            defaults={
                "is_enabled": product_data.get("is_enabled", True),
                "max_single_amount": product_data.get("max_single_amount"),
                "daily_limit": product_data.get("daily_limit"),
            },
        )
        return product
