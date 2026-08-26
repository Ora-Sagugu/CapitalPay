"""RBAC 模型 — 运营后台账号、角色、权限体系。

包含: SystemUser（运营人员账号）、Role（角色）、Permission（权限）、
      UserRole（用户-角色关联）、RolePermission（角色-权限关联）、OperationLog（操作日志）。
"""
from django.db import models
from apps.core.models import BaseModel


class SystemUser(BaseModel):
    """运营后台用户 — B2B 支付平台内部运营人员账号。

    角色包括: 超级管理员、运营、财务、审计、商户管理员等。
    """
    username = models.CharField(max_length=64, unique=True, verbose_name="用户名")
    password_hash = models.CharField(max_length=256, verbose_name="密码哈希")
    real_name = models.CharField(max_length=64, verbose_name="真实姓名")
    phone = models.CharField(max_length=20, blank=True, verbose_name="手机号")
    email = models.EmailField(blank=True, verbose_name="邮箱")
    is_active = models.BooleanField(default=True, verbose_name="启用")
    is_locked = models.BooleanField(default=False, verbose_name="锁定")
    locked_until = models.DateTimeField(null=True, blank=True, verbose_name="锁定至")
    login_failed_count = models.PositiveSmallIntegerField(default=0, verbose_name="登录失败次数")
    last_login_at = models.DateTimeField(null=True, blank=True, verbose_name="最后登录时间")
    last_login_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="最后登录IP")

    class Meta:
        db_table = "system_user"
        verbose_name = "运营后台用户"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    @property
    def is_authenticated(self):
        return True

    def __str__(self):
        return f"{self.real_name}({self.username})"


class Role(BaseModel):
    """角色 — 权限的集合，一个角色包含多个权限。"""

    name = models.CharField(max_length=64, unique=True, verbose_name="角色名称")
    code = models.CharField(max_length=64, unique=True, verbose_name="角色编码")
    description = models.CharField(max_length=256, blank=True, verbose_name="描述")
    is_system = models.BooleanField(default=False, verbose_name="系统内置")

    class Meta:
        db_table = "system_role"
        verbose_name = "角色"
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class Permission(BaseModel):
    """权限 — 最小授权单元，格式: resource:action。

    例如: payment:view, payment:create, merchant:approve, report:export
    """

    class ResourceGroup(models.TextChoices):
        MERCHANT = "merchant", "商户管理"
        PAYMENT = "payment", "支付管理"
        REFUND = "refund", "退款管理"
        ACCOUNT = "account", "账户管理"
        RECONCILIATION = "reconciliation", "对账管理"
        SETTLEMENT = "settlement", "清算管理"
        REPORT = "report", "报表查询"
        SYSTEM = "system", "系统管理"

    code = models.CharField(max_length=128, unique=True, verbose_name="权限编码")
    name = models.CharField(max_length=128, verbose_name="权限名称")
    resource = models.CharField(
        max_length=64, choices=ResourceGroup.choices, verbose_name="资源模块"
    )
    action = models.CharField(
        max_length=32, verbose_name="操作类型"
    )  # view / create / edit / delete / approve / export
    description = models.CharField(max_length=256, blank=True, verbose_name="描述")

    class Meta:
        db_table = "system_permission"
        verbose_name = "权限"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.code} — {self.name}"


class UserRole(BaseModel):
    """用户-角色关联。一个用户可以有多个角色。"""

    user = models.ForeignKey(SystemUser, on_delete=models.CASCADE, verbose_name="用户")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, verbose_name="角色")

    class Meta:
        db_table = "user_role"
        unique_together = [["user", "role"]]
        verbose_name = "用户角色"
        verbose_name_plural = verbose_name


class RolePermission(BaseModel):
    """角色-权限关联。一个角色包含多个权限。"""

    role = models.ForeignKey(Role, on_delete=models.CASCADE, verbose_name="角色")
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, verbose_name="权限")

    class Meta:
        db_table = "role_permission"
        unique_together = [["role", "permission"]]
        verbose_name = "角色权限"
        verbose_name_plural = verbose_name


class OperationLog(models.Model):
    """操作日志 — 记录运营人员的关键操作。

    补充核心模块的 AuditLog，专注于运营后台操作审计。
    """

    class ActionType(models.TextChoices):
        LOGIN = "LOGIN", "登录"
        LOGOUT = "LOGOUT", "登出"
        CREATE = "CREATE", "创建"
        UPDATE = "UPDATE", "修改"
        DELETE = "DELETE", "删除"
        APPROVE = "APPROVE", "审批"
        EXPORT = "EXPORT", "导出"

    class Status(models.TextChoices):
        SUCCESS = "SUCCESS", "成功"
        FAILED = "FAILED", "失败"

    user = models.ForeignKey(
        SystemUser, on_delete=models.PROTECT, null=True, blank=True, verbose_name="操作人"
    )
    username = models.CharField(max_length=64, verbose_name="用户名快照")
    action = models.CharField(max_length=32, choices=ActionType.choices, verbose_name="操作类型")
    resource = models.CharField(max_length=64, verbose_name="资源类型")
    resource_id = models.CharField(max_length=128, blank=True, verbose_name="资源ID")
    detail = models.JSONField(default=dict, verbose_name="操作详情")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.SUCCESS, verbose_name="状态"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP地址")
    user_agent = models.CharField(max_length=512, blank=True, verbose_name="User-Agent")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="操作时间")

    class Meta:
        db_table = "operation_log"
        verbose_name = "操作日志"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["action", "resource", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RuntimeError("操作日志不可修改")
        super().save(*args, **kwargs)
