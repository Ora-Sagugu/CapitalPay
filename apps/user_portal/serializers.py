"""用户端 DRF 序列化器。"""
from rest_framework import serializers
from .models import EndUser


class RegisterSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(min_length=6, max_length=128)
    sms_code = serializers.CharField(required=False, allow_blank=True)
    nickname = serializers.CharField(required=False, allow_blank=True, max_length=64)


class RegisterByEmailSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=3, max_length=64)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=6, max_length=128)


class LoginByPasswordSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(max_length=128)


class LoginByEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(max_length=128)


class LoginBySmsSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    sms_code = serializers.CharField(max_length=6)


class SmsCodeSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    scene = serializers.ChoiceField(
        choices=["REGISTER", "LOGIN", "RESET_PASSWORD", "BIND_ACCOUNT"]
    )


class ResetPasswordSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    sms_code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(min_length=6, max_length=128)


class RefreshTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class ProfileUpdateSerializer(serializers.Serializer):
    nickname = serializers.CharField(required=False, max_length=64)
    email = serializers.EmailField(required=False, allow_blank=True)
    avatar_url = serializers.CharField(required=False, allow_blank=True)


class IdentityVerifySerializer(serializers.Serializer):
    real_name = serializers.CharField(max_length=64)
    id_card = serializers.CharField(max_length=18)


class OnboardingBasicSerializer(serializers.Serializer):
    legal_name = serializers.CharField(max_length=128)
    id_type = serializers.CharField(max_length=32)
    id_number = serializers.CharField(max_length=128)
    contact_phone = serializers.CharField(max_length=20)
    nationality = serializers.CharField(required=False, allow_blank=True, max_length=64)
    address = serializers.CharField(required=False, allow_blank=True, max_length=512)
    agent_code = serializers.CharField(required=False, allow_blank=True, max_length=64)
    license_expiry_date = serializers.DateField(required=False, allow_null=True)


class OnboardingFinanceSerializer(serializers.Serializer):
    bank_name = serializers.CharField(max_length=256)
    branch_name = serializers.CharField(required=False, allow_blank=True, max_length=256)
    bank_account = serializers.CharField(max_length=128)


class OnboardingImagesSerializer(serializers.Serializer):
    license_image = serializers.CharField()
    id_front_image = serializers.CharField()
    id_back_image = serializers.CharField()


class OnboardingSubmitSerializer(serializers.Serializer):
    basic = OnboardingBasicSerializer()
    finance = OnboardingFinanceSerializer()
    images = OnboardingImagesSerializer()


class OnboardingReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    remark = serializers.CharField(required=False, allow_blank=True, max_length=512)


class EndUserAdminListSerializer(serializers.Serializer):
    """运营后台 — 终端用户列表序列化器"""
    id = serializers.CharField()
    username = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField()
    nickname = serializers.CharField()
    real_name = serializers.CharField()
    is_active = serializers.BooleanField()
    is_verified = serializers.BooleanField()
    onboarding_status = serializers.CharField()
    last_login_at = serializers.DateTimeField()
    created_at = serializers.DateTimeField()
    merchant_no = serializers.CharField()
    merchant_name = serializers.CharField()
    merchant_status = serializers.CharField()


class BindMerchantSerializer(serializers.Serializer):
    """运营后台 — 绑定/解绑用户默认商户"""
    merchant_no = serializers.CharField(max_length=32)
