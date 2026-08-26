"""清结算 — Django Admin 注册。"""
from django.contrib import admin
from .models import SettlementBatch, SettlementDetail, FeeShare, DifferenceWriteOff


@admin.register(SettlementBatch)
class SettlementBatchAdmin(admin.ModelAdmin):
    list_display = ["batch_no", "merchant", "settle_date", "total_count", "total_amount", "settle_net_amount", "status"]
    list_filter = ["status", "settle_date"]
    search_fields = ["batch_no", "merchant__merchant_name"]


@admin.register(SettlementDetail)
class SettlementDetailAdmin(admin.ModelAdmin):
    list_display = ["order_no", "amount", "fee", "settle_amount", "created_at"]
    search_fields = ["order_no"]


@admin.register(FeeShare)
class FeeShareAdmin(admin.ModelAdmin):
    list_display = ["settlement_detail", "channel_fee", "platform_fee", "agent_fee"]


@admin.register(DifferenceWriteOff)
class DifferenceWriteOffAdmin(admin.ModelAdmin):
    list_display = ["write_off_no", "merchant", "amount", "status", "applied_by"]
    list_filter = ["status"]
