"""基础抽象模型 — 所有业务模型继承自 BaseModel。"""
from django.db import models
import uuid


class BaseModel(models.Model):
    """抽象基础模型，提供 id、创建时间、更新时间。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    is_deleted = models.BooleanField(default=False, verbose_name="软删除")

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class AuditLog(models.Model):
    """操作审计日志 — append-only，不可修改。"""

    operator = models.CharField(max_length=64, verbose_name="操作人")
    action = models.CharField(max_length=64, verbose_name="操作类型")  # CREATE / UPDATE / DELETE / APPROVE
    resource_type = models.CharField(max_length=64, verbose_name="资源类型")
    resource_id = models.CharField(max_length=64, verbose_name="资源ID")
    before_snapshot = models.JSONField(null=True, blank=True, verbose_name="变更前")
    after_snapshot = models.JSONField(null=True, blank=True, verbose_name="变更后")
    ip_address = models.GenericIPAddressField(null=True, verbose_name="IP地址")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="操作时间")

    class Meta:
        db_table = "audit_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["operator", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        """AuditLog 只允许创建，不允许修改。"""
        if self.pk is not None:
            raise RuntimeError("审计日志不可修改")
        super().save(*args, **kwargs)
