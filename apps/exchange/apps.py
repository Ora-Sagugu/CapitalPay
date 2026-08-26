"""汇率管理应用配置。"""


from django.apps import AppConfig


class ExchangeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.exchange"
    verbose_name = "汇率管理"
