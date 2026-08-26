# apps/reconciliation/apps.py
from django.apps import AppConfig


class ReconciliationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reconciliation"
    verbose_name = "对账引擎"
