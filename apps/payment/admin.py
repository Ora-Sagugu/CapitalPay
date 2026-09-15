"""支付交易 — Django Admin 注册。"""
from django.contrib import admin
from .models import BankCreditNotification, PaymentOrder, RefundOrder


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    list_display = ["order_no", "merchant_order_no", "amount", "fee_amount", "status", "pay_method", "created_at"]
    list_filter = ["status", "pay_method", "created_at"]
    search_fields = ["order_no", "merchant_order_no", "unique_identification_no", "bank_txn_id"]
    readonly_fields = ["order_no", "unique_identification_no", "status_history"]
    ordering = ["-created_at"]


@admin.register(RefundOrder)
class RefundOrderAdmin(admin.ModelAdmin):
    list_display = ["refund_no", "payment_order", "refund_amount", "status", "reviewed_at", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["refund_no", "payment_order__order_no"]
    ordering = ["-created_at"]


@admin.register(BankCreditNotification)
class BankCreditNotificationAdmin(admin.ModelAdmin):
    list_display = [
        "notification_no", "prn_code", "order_no", "merchant_name",
        "bank_name", "amount", "currency", "status", "txn_time",
    ]
    list_filter = ["status", "source", "currency"]
    search_fields = ["notification_no", "prn_code", "order_no", "merchant_name", "txn_id"]
    ordering = ["-txn_time"]
    readonly_fields = ["notification_no", "txn_id", "raw_payload"]
