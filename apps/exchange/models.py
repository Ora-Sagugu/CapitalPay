from django.db import models
from apps.core.models import BaseModel

class ExchangeRate(BaseModel):
    date = models.DateField(verbose_name="日期")
    from_currency = models.CharField(max_length=3, verbose_name="汇出币种")
    to_currency = models.CharField(max_length=3, verbose_name="到账币种")
    rate = models.DecimalField(max_digits=18, decimal_places=8, verbose_name="汇率")
    source = models.CharField(max_length=64, default="Bloomberg", verbose_name="来源")

    class Meta:
        db_table = "exchange_rate"
        verbose_name = "汇率"
        verbose_name_plural = verbose_name
        ordering = ["-date", "from_currency", "to_currency"]
        unique_together = [["date", "from_currency", "to_currency"]]
