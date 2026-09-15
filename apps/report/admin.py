"""财务报表 — Django Admin 注册。"""
from django.contrib import admin
from .models import MerchantDailyReport, ChannelFeeReport, PlatformOrderSummary


@admin.register(MerchantDailyReport)
class MerchantDailyReportAdmin(admin.ModelAdmin):
    list_display = ["report_date", "merchant", "currency", "total_orders", "total_amount", "total_fee", "net_amount"]
    list_filter = ["report_date", "currency"]


@admin.register(ChannelFeeReport)
class ChannelFeeReportAdmin(admin.ModelAdmin):
    list_display = ["report_date", "bank_code", "bank_name", "currency", "total_orders", "total_amount", "channel_fee", "platform_fee"]
    list_filter = ["report_date", "bank_code", "currency"]


@admin.register(PlatformOrderSummary)
class PlatformOrderSummaryAdmin(admin.ModelAdmin):
    list_display = ["report_date", "currency", "total_merchants", "total_orders", "total_amount", "total_fee", "settled_amount"]
    list_filter = ["report_date", "currency"]
