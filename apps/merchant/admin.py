"""商户管理 — Django Admin 注册。"""
from django.contrib import admin
from .models import Merchant, MerchantKYC, MerchantFee, MerchantSettlementAccount, MerchantPaymentProduct


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ["merchant_no", "merchant_name", "short_name", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["merchant_no", "merchant_name"]


@admin.register(MerchantKYC)
class MerchantKYCAdmin(admin.ModelAdmin):
    list_display = ["merchant", "legal_person", "created_at"]
    search_fields = ["merchant__merchant_name", "legal_person"]


@admin.register(MerchantFee)
class MerchantFeeAdmin(admin.ModelAdmin):
    list_display = ["merchant", "product_type", "fee_model", "fixed_fee", "fee_rate", "effective_from"]
    list_filter = ["product_type", "fee_model"]


@admin.register(MerchantSettlementAccount)
class MerchantSettlementAccountAdmin(admin.ModelAdmin):
    list_display = ["merchant", "bank_name", "account_name", "is_default"]


@admin.register(MerchantPaymentProduct)
class MerchantPaymentProductAdmin(admin.ModelAdmin):
    list_display = ["merchant", "product_type", "is_enabled", "max_single_amount", "daily_limit"]
