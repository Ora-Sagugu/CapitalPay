"""RBAC 路由 — 运营后台认证、用户管理、角色、权限。"""
from rest_framework.routers import DefaultRouter
from .views import (
    AuthViewSet, SystemUserViewSet, RoleViewSet,
    PermissionViewSet, OperationLogViewSet, FunctionViewSet,
)

router = DefaultRouter()
router.register(r"auth", AuthViewSet, basename="rbac-auth")
router.register(r"users", SystemUserViewSet, basename="rbac-user")
router.register(r"roles", RoleViewSet, basename="rbac-role")
router.register(r"permissions", PermissionViewSet, basename="rbac-permission")
router.register(r"functions", FunctionViewSet, basename="rbac-function")
router.register(r"logs", OperationLogViewSet, basename="rbac-log")

urlpatterns = router.urls
