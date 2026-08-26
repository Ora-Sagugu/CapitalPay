"""账户体系 — Django Admin 注册。"""
from django.contrib import admin
from .models import NostroAccount, UserAccount, FundTransfer, UserPaymentDetail, VirtualAccount


@admin.register(NostroAccount)
class NostroAccountAdmin(admin.ModelAdmin):
    list_display = ["account_no", "bank_code", "bank_name", "account_type", "currency", "balance", "is_active"]
    list_filter = ["bank_code", "account_type", "is_active"]
    search_fields = ["account_no", "bank_name"]


@admin.register(VirtualAccount)
class VirtualAccountAdmin(admin.ModelAdmin):
    list_display = ["va_number", "va_type", "master_account", "merchant", "currency", "status", "opened_at"]
    list_filter = ["va_type", "status", "currency", "country"]
    search_fields = ["va_number", "reference", "label", "merchant__merchant_name"]
    raw_id_fields = ["master_account", "merchant", "order"]


@admin.register(UserAccount)
class UserAccountAdmin(admin.ModelAdmin):
    list_display = ["user_id", "bank_code", "account_holder", "status", "bind_at"]
    list_filter = ["status", "bank_code"]
    search_fields = ["user_id", "account_holder"]


@admin.register(FundTransfer)
class FundTransferAdmin(admin.ModelAdmin):
    list_display = ["transfer_no", "from_account", "to_account", "amount", "status", "executed_at"]
    list_filter = ["status"]


@admin.register(UserPaymentDetail)
class UserPaymentDetailAdmin(admin.ModelAdmin):
    list_display = ["user_id", "order", "amount", "pay_method", "pay_time"]
    search_fields = ["user_id"]
