# apps/merchant/apps.py
from django.apps import AppConfig


class MerchantConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.merchant"
    verbose_name = "商户管理"

    def ready(self):
        # 注册信号：新商户自动开通账户
        from . import signals  # noqa: F401
