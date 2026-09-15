"""用户端 DRF 序列化器。"""
from rest_framework import serializers
from .models import EndUser


def _normalize_gmail(value: str) -> str:
    """Only @gmail.com addresses are accepted. Stored/queried in lowercase."""
    email = (value or "").strip().lower()
    if not email.endswith("@gmail.com") or email.count("@") != 1 or email.startswith("@"):
        raise serializers.ValidationError("Only @gmail.com email addresses are allowed")
    if not email.split("@", 1)[0]:
        raise serializers.ValidationError("Only @gmail.com email addresses are allowed")
    return email


class RegisterSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(min_length=6, max_length=128)
    sms_code = serializers.CharField(required=False, allow_blank=True)
    nickname = serializers.CharField(required=False, allow_blank=True, max_length=64)
    portal_role = serializers.ChoiceField(choices=["customer", "agent"], required=False)


class RegisterByEmailSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True, max_length=64)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=6, max_length=128)
    portal_role = serializers.ChoiceField(choices=["customer", "agent"], required=False)

    def validate_email(self, value):
        return _normalize_gmail(value)

    def validate(self, attrs):
        email = attrs["email"]
        username = (attrs.get("username") or "").strip()
        if not username:
            username = email.split("@", 1)[0]
        if len(username) < 3:
            raise serializers.ValidationError({"username": "Username must be at least 3 characters"})
        attrs["username"] = username
        return attrs


class LoginByPasswordSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(max_length=128)
    portal_role = serializers.ChoiceField(choices=["customer", "agent"], required=False)


class LoginByEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(max_length=128)
    portal_role = serializers.ChoiceField(choices=["customer", "agent"], required=False)

    def validate_email(self, value):
        return _normalize_gmail(value)


class LoginBySmsSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    sms_code = serializers.CharField(max_length=6)
    portal_role = serializers.ChoiceField(choices=["customer", "agent"], required=False)


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

    def validate_email(self, value):
        if value in (None, ""):
            return value
        return _normalize_gmail(value)


class ChooseRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["customer", "agent"])


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
    bank_name = serializers.CharField(required=False, allow_blank=True, max_length=256)
    branch_name = serializers.CharField(required=False, allow_blank=True, max_length=256)
    account_name = serializers.CharField(required=False, allow_blank=True, max_length=256)
    bank_account = serializers.CharField(required=False, allow_blank=True, max_length=128)
    swift_code = serializers.CharField(required=False, allow_blank=True, max_length=16)


class OnboardingImagesSerializer(serializers.Serializer):
    license_image = serializers.CharField()
    id_front_image = serializers.CharField()
    id_back_image = serializers.CharField()


class OnboardingSubmitSerializer(serializers.Serializer):
    basic = OnboardingBasicSerializer()
    finance = OnboardingFinanceSerializer(required=False)
    images = OnboardingImagesSerializer()


class OnboardingReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    remark = serializers.CharField(required=False, allow_blank=True, max_length=512)


class AgentOrderReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["agree", "reject", "approve"])
    remark = serializers.CharField(required=False, allow_blank=True, max_length=512)


class AgentRemittanceQuoteSerializer(serializers.Serializer):
    merchant_id = serializers.CharField(max_length=64)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=0.01)
    from_currency = serializers.CharField(max_length=3, default="USD")
    to_currency = serializers.CharField(max_length=3, default="CNY")
    fee_bearing = serializers.ChoiceField(choices=["OUR", "SHA", "BEN"], default="OUR")

    def validate_from_currency(self, value):
        return value.upper()

    def validate_to_currency(self, value):
        return value.upper()


class AgentRemittanceSubmitSerializer(serializers.Serializer):
    merchant_id = serializers.CharField(max_length=64)
    quote_id = serializers.CharField(max_length=40)
    beneficiary_name = serializers.CharField(max_length=128, trim_whitespace=True)
    beneficiary_bank = serializers.CharField(max_length=128, trim_whitespace=True)
    beneficiary_account = serializers.CharField(max_length=64, trim_whitespace=True)
    beneficiary_swift = serializers.CharField(
        max_length=16, required=False, allow_blank=True, allow_null=True
    )
    beneficiary_address = serializers.CharField(
        max_length=256, required=False, allow_blank=True, allow_null=True
    )
    remittance_purpose = serializers.CharField(
        max_length=256, required=False, allow_blank=True, allow_null=True
    )
    contract_file = serializers.CharField(
        max_length=512, required=False, allow_blank=True, allow_null=True
    )

    def validate(self, attrs):
        for field in (
            "beneficiary_swift", "beneficiary_address",
            "remittance_purpose", "contract_file",
        ):
            attrs[field] = attrs.get(field) or ""
        return attrs


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
