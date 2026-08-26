"""Sanctions / Compliance models — 制裁名单扫描"""
from datetime import date, timedelta
from django.db import models
from apps.core.models import BaseModel


class SanctionList(BaseModel):
    """制裁名单"""
    RISK_LEVELS = (
        ("HIGH", "高风险"),
        ("MEDIUM", "中风险"),
        ("LOW", "低风险"),
    )
    LIST_TYPES = (
        ("OFAC", "OFAC(美国)"),
        ("UN", "联合国"),
        ("EU", "欧盟"),
        ("MPS", "公安部"),
        ("PBOC", "人民银行"),
        ("INTERNAL", "内部黑名单"),
    )
    ENTITY_TYPES = (
        ("PERSON", "个人"),
        ("COMPANY", "企业"),
        ("CITY", "城市"),
        ("COUNTRY", "国家"),
        ("VESSEL", "船只"),
        ("OTHER", "其他"),
    )
    entity_name = models.CharField("实体名称", max_length=256, db_index=True)
    alias_names = models.TextField("别名(逗号分隔)", blank=True)
    reference_id = models.CharField("名单编号", max_length=32, blank=True, db_index=True,
                                    help_text="制裁名单中的唯一编号，如 QDi.371, KPe.030")
    entity_type = models.CharField("实体类型", max_length=32, choices=ENTITY_TYPES, default="PERSON")
    list_type = models.CharField("名单来源", max_length=16, choices=LIST_TYPES)
    risk_level = models.CharField("风险等级", max_length=8, choices=RISK_LEVELS, default="MEDIUM")
    id_number = models.CharField("证件号码", max_length=256, blank=True)
    nationality = models.CharField("国籍", max_length=64, blank=True)
    date_of_birth = models.CharField("出生日期", max_length=64, blank=True)
    place_of_birth = models.CharField("出生地点", max_length=256, blank=True)
    address = models.TextField("地址", blank=True)
    country = models.CharField("国家/地区", max_length=64, blank=True)
    sanction_reason = models.TextField("制裁原因", blank=True)
    effective_date = models.DateField("生效日期(列入名单日期)", null=True, blank=True)
    expiry_date = models.DateField("失效日期", null=True, blank=True)
    review_date = models.DateField("复审日期", null=True, blank=True,
                                   help_text="根据风险等级自动计算: HIGH=30天 / MEDIUM=90天 / LOW=180天")
    is_active = models.BooleanField("是否有效", default=True)

    REVIEW_DAYS = {"HIGH": 30, "MEDIUM": 90, "LOW": 180}

    def save(self, *args, **kwargs):
        """自动设置复审日期：风险等级变更或复审日期为空时，根据风险等级重新计算"""
        if self.risk_level and self.risk_level in self.REVIEW_DAYS:
            # 只有在 review_date 为空、或风险等级发生变化时自动设置
            if not self.review_date:
                self.review_date = date.today() + timedelta(days=self.REVIEW_DAYS[self.risk_level])
            elif self.pk:
                try:
                    old = SanctionList.objects.only("risk_level").get(pk=self.pk)
                    if old.risk_level != self.risk_level:
                        self.review_date = date.today() + timedelta(days=self.REVIEW_DAYS[self.risk_level])
                except SanctionList.DoesNotExist:
                    pass
        super().save(*args, **kwargs)

    class Meta:
        db_table = "sanction_list"
        verbose_name = "制裁名单"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["entity_name", "list_type"]),
            models.Index(fields=["risk_level", "is_active"]),
        ]
        ordering = ["-risk_level", "entity_name"]

    def __str__(self):
        return f"[{self.get_list_type_display()}] {self.entity_name}"


class SanctionScanRecord(BaseModel):
    """制裁名单扫描记录"""
    SCAN_STATUS = (
        ("PENDING", "待扫描"),
        ("SCANNING", "扫描中"),
        ("CLEAR", "通过"),
        ("HIT", "命中"),
        ("MANUAL_REVIEW", "人工复核"),
    )
    SCAN_TYPES = (
        ("TRANSACTION", "交易扫描"),
        ("MERCHANT_ONBOARDING", "商户入驻"),
        ("AGENT_ONBOARDING", "代理入驻"),
        ("BATCH", "批量扫描"),
    )
    scan_no = models.CharField("扫描编号", max_length=32, unique=True, db_index=True)
    scan_type = models.CharField("扫描类型", max_length=32, choices=SCAN_TYPES)
    target_type = models.CharField("目标类型", max_length=32)
    target_id = models.CharField("目标ID", max_length=64)
    target_name = models.CharField("目标名称", max_length=256)
    status = models.CharField("状态", max_length=16, choices=SCAN_STATUS, default="PENDING")
    hit_count = models.IntegerField("命中数", default=0)
    operator = models.CharField("操作人", max_length=64, blank=True)
    scan_result = models.JSONField("扫描结果", default=dict)

    class Meta:
        db_table = "sanction_scan_record"
        verbose_name = "制裁扫描记录"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return self.scan_no


class SanctionHitDetail(BaseModel):
    """制裁扫描命中明细"""
    scan_record = models.ForeignKey(
        SanctionScanRecord, on_delete=models.CASCADE, related_name="hits", verbose_name="扫描记录"
    )
    sanction_entry = models.ForeignKey(
        SanctionList, on_delete=models.PROTECT, related_name="hits", verbose_name="命中名单"
    )
    match_field = models.CharField("匹配字段", max_length=64)
    match_value = models.CharField("匹配值", max_length=512)
    match_score = models.FloatField("匹配分数", default=0)
    is_resolved = models.BooleanField("已处理", default=False)
    resolution = models.CharField("处理结果", max_length=16, choices=(
        ("TRUE_HIT", "确认命中"), ("FALSE_POSITIVE", "误报"), ("PENDING", "待处理"),
    ), default="PENDING")
    resolved_by = models.CharField("处理人", max_length=64, blank=True)
    resolved_at = models.DateTimeField("处理时间", null=True, blank=True)
    remark = models.TextField("备注", blank=True)

    class Meta:
        db_table = "sanction_hit_detail"
        verbose_name = "制裁命中明细"
        verbose_name_plural = verbose_name
        ordering = ["-match_score"]
