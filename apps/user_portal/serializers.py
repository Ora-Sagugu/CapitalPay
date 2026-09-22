"""用户端 DRF 序列化器。"""
from rest_framework import serializers

from .models import EndUser


def _normalize_email(value: str) -> str:
    """Accept any well-formed email; store/query in lowercase."""
    email = (value or "").strip().lower()
    if email.count("@") != 1 or email.startswith("@") or email.endswith("@"):
        raise serializers.ValidationError("Enter a valid email address")
    local, domain = email.split("@", 1)
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise serializers.ValidationError("Enter a valid email address")
    return email


class RegisterSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(min_length=6, max_length=128)
    sms_code = serializers.CharField(required=False, allow_blank=True)
    nickname = serializers.CharField(required=False, allow_blank=True, max_length=64)
    portal_role = serializers.ChoiceField(choices=["merchant", "agent"], required=False)


class RegisterByEmailSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True, max_length=64)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=6, max_length=128)
    portal_role = serializers.ChoiceField(choices=["merchant", "agent"], required=False)

    def validate_email(self, value):
        return _normalize_email(value)

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
    portal_role = serializers.ChoiceField(choices=["merchant", "agent"], required=False)


class LoginByEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(max_length=128)
    portal_role = serializers.ChoiceField(choices=["merchant", "agent"], required=False)

    def validate_email(self, value):
        return _normalize_email(value)


class LoginBySmsSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    sms_code = serializers.CharField(max_length=6)
    portal_role = serializers.ChoiceField(choices=["merchant", "agent"], required=False)


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
        return _normalize_email(value)


class ChooseRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["merchant", "agent"])


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
    trading_market = serializers.CharField(required=False, allow_blank=True, max_length=32)
    trn = serializers.CharField(required=False, allow_blank=True, max_length=64)


class OnboardingFinanceSerializer(serializers.Serializer):
    bank_name = serializers.CharField(required=False, allow_blank=True, max_length=256)
    branch_name = serializers.CharField(required=False, allow_blank=True, max_length=256)
    account_name = serializers.CharField(required=False, allow_blank=True, max_length=256)
    bank_account = serializers.CharField(required=False, allow_blank=True, max_length=128)
    swift_code = serializers.CharField(required=False, allow_blank=True, max_length=16)


class OnboardingImagesSerializer(serializers.Serializer):
    license_image = serializers.CharField(required=False, allow_blank=True)
    id_front_image = serializers.CharField(required=False, allow_blank=True)
    id_back_image = serializers.CharField(required=False, allow_blank=True)
    # Aliases used by the simplified merchant profile form.
    government_id_image = serializers.CharField(required=False, allow_blank=True)
    proof_of_address_image = serializers.CharField(required=False, allow_blank=True)
    trn_certificate_image = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        # Map friendly aliases onto the persisted image columns.
        if attrs.get("government_id_image") and not attrs.get("id_front_image"):
            attrs["id_front_image"] = attrs["government_id_image"]
        if attrs.get("proof_of_address_image") and not attrs.get("id_back_image"):
            attrs["id_back_image"] = attrs["proof_of_address_image"]
        if attrs.get("trn_certificate_image") and not attrs.get("license_image"):
            attrs["license_image"] = attrs["trn_certificate_image"]
        return attrs


def _derive_onboarding_from_kyb(kyb: dict) -> dict:
    """Map CapitalPay Merchant KYB payload into legacy basic/finance/images."""
    business = kyb.get("business") or {}
    people = kyb.get("people") or []
    payout = kyb.get("payout") or {}
    docs = kyb.get("kyb_documents") or {}
    primary = next(
        (p for p in people if "signator" in str(p.get("role") or "").lower()),
        people[0] if people else {},
    )
    id_type_raw = str(primary.get("id_type") or "").lower()
    if "passport" in id_type_raw:
        id_type = "passport"
    elif "licence" in id_type_raw or "license" in id_type_raw or "nrc" in id_type_raw or "national" in id_type_raw:
        id_type = "id_card"
    else:
        id_type = "business_license" if (kyb.get("account_type") or "") != "individual" else "id_card"

    license_image = (
        docs.get("coi")
        or docs.get("cor")
        or docs.get("secreg")
        or docs.get("cert")
        or docs.get("id")
        or next(iter(docs.values()), "")
    )
    id_doc = primary.get("id_document") or ""
    return {
        "basic": {
            "legal_name": business.get("legal_name") or "",
            "id_type": id_type,
            "id_number": primary.get("id_number") or business.get("tax_id") or "",
            "contact_phone": business.get("phone") or "",
            "nationality": primary.get("nationality_type") or "",
            "address": business.get("address") or "",
            "agent_code": (kyb.get("agent_code") or "").strip(),
            "license_expiry_date": primary.get("id_expiry") or None,
        },
        "finance": {
            "bank_name": payout.get("bank") or "",
            "branch_name": "",
            "account_name": payout.get("account_name") or "",
            "bank_account": payout.get("account_number") or "",
            "swift_code": "",
        },
        "images": {
            "license_image": license_image or id_doc or "",
            "id_front_image": id_doc or license_image or "",
            "id_back_image": id_doc or license_image or "",
        },
    }


class OnboardingSubmitSerializer(serializers.Serializer):
    # DictField (not nested serializers): KYB payloads may send a partial `basic`
    # (e.g. only agent_code). Full validation runs in validate() after derivation.
    basic = serializers.DictField(required=False)
    finance = serializers.DictField(required=False)
    images = serializers.DictField(required=False)
    kyb = serializers.DictField(required=False)

    def validate(self, attrs):
        kyb = attrs.get("kyb")
        if kyb:
            derived = _derive_onboarding_from_kyb(kyb)
            attrs["basic"] = {**derived["basic"], **(attrs.get("basic") or {})}
            attrs["finance"] = {**derived["finance"], **(attrs.get("finance") or {})}
            attrs["images"] = {**derived["images"], **(attrs.get("images") or {})}
            attrs["application_ref"] = (
                (kyb.get("application_ref") or "")
                or ((kyb.get("settlement_mandate") or {}).get("reference") or "")
            )
        if not attrs.get("basic"):
            raise serializers.ValidationError({"basic": "This field is required."})
        basic_s = OnboardingBasicSerializer(data=attrs["basic"])
        basic_s.is_valid(raise_exception=True)
        attrs["basic"] = basic_s.validated_data
        if attrs.get("finance") is not None:
            finance_s = OnboardingFinanceSerializer(data=attrs.get("finance") or {})
            finance_s.is_valid(raise_exception=True)
            attrs["finance"] = finance_s.validated_data
        images_s = OnboardingImagesSerializer(data=attrs.get("images") or {})
        images_s.is_valid(raise_exception=True)
        attrs["images"] = images_s.validated_data
        return attrs


class AgentReferralReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    remark = serializers.CharField(required=False, allow_blank=True, max_length=512)


class OnboardingReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    remark = serializers.CharField(required=False, allow_blank=True, max_length=512)
    risk_level = serializers.ChoiceField(choices=["LOW", "MEDIUM", "HIGH"], required=False)
    enable_wire_transfer = serializers.BooleanField(required=False)
    fee_model = serializers.ChoiceField(choices=["FIXED", "PERCENTAGE", "TIERED"], required=False)
    fee_rate = serializers.DecimalField(max_digits=8, decimal_places=6, required=False)
    fixed_fee = serializers.DecimalField(max_digits=12, decimal_places=4, required=False)
    min_fee = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    max_fee = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    max_single_amount = serializers.DecimalField(
        max_digits=18, decimal_places=2, required=False, allow_null=True,
    )
    daily_limit = serializers.DecimalField(
        max_digits=18, decimal_places=2, required=False, allow_null=True,
    )
    daily_count = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    kyc_tier = serializers.ChoiceField(choices=["TIER_1", "TIER_2", "TIER_3"], required=False)
    commission_rate = serializers.DecimalField(
        max_digits=8, decimal_places=6, required=False, min_value=0, max_value=1,
    )

    def validate(self, attrs):
        if attrs["action"] == "reject":
            if not (attrs.get("remark") or "").strip():
                raise serializers.ValidationError({"remark": "Grounds for rejection are required"})
            return attrs
        portal_role = self.context.get("portal_role") or "merchant"
        errors = {}
        if portal_role == "agent":
            attrs.setdefault("kyc_tier", "TIER_1")
            if attrs.get("commission_rate") is None:
                from decimal import Decimal
                attrs["commission_rate"] = Decimal("0")
        else:
            if not attrs.get("risk_level"):
                errors["risk_level"] = "Risk level is required"
            if attrs.get("enable_wire_transfer") is not True:
                errors["enable_wire_transfer"] = "Wire transfer must be enabled to activate the merchant"
            if not attrs.get("fee_model"):
                errors["fee_model"] = "Fee model is required"
            if attrs.get("fee_rate") is None:
                errors["fee_rate"] = "Fee rate is required"
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


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
