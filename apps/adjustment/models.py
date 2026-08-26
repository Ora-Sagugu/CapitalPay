import uuid
from typing import Optional
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class AdjustmentApplication(models.Model):
    """差异账调账申请"""

    class Status(models.TextChoices):
        PENDING = "pending", "待审批"
        APPROVED = "approved", "已通过"
        REJECTED = "rejected", "已拒绝"
        CANCELLED = "cancelled", "已取消"
        COMPLETED = "completed", "已完成"

    class DiffType(models.TextChoices):
        AMOUNT = "amount", "金额差异"
        COUNT = "count", "笔数差异"
        STATUS = "status", "状态差异"
        DUPLICATE = "duplicate", "重复交易"
        MISSING = "missing", "缺失交易"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application_no = models.CharField("申请单号", max_length=64, unique=True)
    diff_type = models.CharField("差异类型", max_length=20, choices=DiffType.choices, default=DiffType.AMOUNT)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.PENDING)
    order_no = models.CharField("关联订单号", max_length=64, blank=True)
    bank_channel = models.CharField("银行通道", max_length=100, blank=True)
    amount = models.DecimalField("差异金额", max_digits=18, decimal_places=2, default=0)
    currency = models.CharField("币种", max_length=10, default="CNY")
    reason = models.TextField("差异原因")
    adjustment_amount = models.DecimalField("调账金额", max_digits=18, decimal_places=2, default=0)
    applicant = models.CharField("申请人", max_length=50)
    applicant_id = models.CharField("申请人ID", max_length=64, blank=True)
    applied_at = models.DateTimeField("申请时间", auto_now_add=True)
    completed_at = models.DateTimeField("完成时间", blank=True, null=True)
    remark = models.TextField("备注", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "adjustment_application"
        verbose_name = "调账申请"
        verbose_name_plural = "调账申请"
        ordering = ["-applied_at"]

    def __str__(self) -> str:
        return f"{self.application_no} ({self.status})"


class AdjustmentApproval(models.Model):
    """调账审批记录"""

    class Action(models.TextChoices):
        APPROVE = "approve", "通过"
        REJECT = "reject", "拒绝"
        RETURN = "return", "退回"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(AdjustmentApplication, on_delete=models.CASCADE, related_name="approvals", verbose_name="调账申请")
    approver = models.CharField("审批人", max_length=50)
    approver_id = models.CharField("审批人ID", max_length=64, blank=True)
    action = models.CharField("审批动作", max_length=20, choices=Action.choices)
    comment = models.TextField("审批意见", blank=True)
    approved_at = models.DateTimeField("审批时间", auto_now_add=True)
    level = models.IntegerField("审批层级", default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])

    class Meta:
        db_table = "adjustment_approval"
        verbose_name = "调账审批"
        verbose_name_plural = "调账审批"
        ordering = ["-approved_at"]

    def __str__(self) -> str:
        return f"{self.application.application_no} - {self.approver} ({self.action})"
