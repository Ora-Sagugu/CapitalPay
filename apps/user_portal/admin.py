"""Django Admin 注册用户端模型。"""
from django.contrib import admin
from .models import EndUser, SmsCode, RefreshToken


@admin.register(EndUser)
class EndUserAdmin(admin.ModelAdmin):
    list_display = ["phone", "nickname", "real_name", "is_verified", "is_active", "last_login_at"]
    list_filter = ["is_verified", "is_active"]
    search_fields = ["phone", "nickname", "real_name"]


@admin.register(SmsCode)
class SmsCodeAdmin(admin.ModelAdmin):
    list_display = ["phone", "scene", "code", "is_used", "expires_at", "created_at"]
    list_filter = ["scene", "is_used"]
    search_fields = ["phone"]


@admin.register(RefreshToken)
class RefreshTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "is_revoked", "expires_at", "created_at"]
    list_filter = ["is_revoked"]
