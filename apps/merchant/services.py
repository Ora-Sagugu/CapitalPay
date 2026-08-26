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
from .models import Merchant, MerchantKYC, MerchantFee, MerchantSettlementAccount, MerchantPaymentProduct


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
        bank_name="Techtanium Nostro",
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
            },
        )
        return kyc

    def get_kyc(self, merchant: Merchant) -> dict:
        """获取商户 KYC — 敏感字段解密。"""
        try:
            kyc = merchant.kyc
            return {
                "merchant_no": merchant.merchant_no,
                "legal_person": kyc.legal_person,
                "id_number": decrypt_field(kyc.id_number),
                "business_license": decrypt_field(kyc.business_license),
                "business_scope": kyc.business_scope,
                "registered_capital": str(kyc.registered_capital) if kyc.registered_capital else None,
                "established_date": str(kyc.established_date),
                "registered_address": kyc.registered_address,
            }
        except MerchantKYC.DoesNotExist:
            return {"merchant_no": merchant.merchant_no}

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
        """计算手续费。

        Returns:
            {"fee_amount": Decimal, "settle_amount": Decimal, "fee_model": str}
        """
        fee_config = self.get_current_fee(merchant, product_type)
        if not fee_config:
            raise BusinessException(ErrorCode.FEE_NOT_CONFIGURED)

        if fee_config.fee_model == MerchantFee.FeeModel.FIXED:
            fee_amount = fee_config.fixed_fee
        elif fee_config.fee_model == MerchantFee.FeeModel.PERCENTAGE:
            fee_amount = amount * fee_config.fee_rate
            fee_amount = max(fee_amount, fee_config.min_fee)
            if fee_config.max_fee:
                fee_amount = min(fee_amount, fee_config.max_fee)
        else:
            fee_amount = Decimal("0")  # TIERED 需要额外实现

        settle_amount = amount - fee_amount
        return {
            "fee_amount": fee_amount,
            "settle_amount": settle_amount,
            "fee_model": fee_config.fee_model,
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
