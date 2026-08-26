"""对账 — Django Admin 注册。"""
from django.contrib import admin
from .models import ReconciliationBatch, ReconciliationDiff, NostroBalanceCheck


@admin.register(ReconciliationBatch)
class ReconciliationBatchAdmin(admin.ModelAdmin):
    list_display = ["batch_no", "bank_code", "reconciliation_date", "diff_count", "status", "created_at"]
    list_filter = ["bank_code", "status", "reconciliation_date"]
    search_fields = ["batch_no"]


@admin.register(ReconciliationDiff)
class ReconciliationDiffAdmin(admin.ModelAdmin):
    list_display = ["diff_type", "order_no", "bank_txn_id", "amount_bank", "amount_platform", "resolution"]
    list_filter = ["diff_type", "resolution"]


@admin.register(NostroBalanceCheck)
class NostroBalanceCheckAdmin(admin.ModelAdmin):
    list_display = ["check_date", "nostro_account", "platform_balance", "bank_statement_balance", "difference", "is_balanced"]
    list_filter = ["check_date", "is_balanced"]
