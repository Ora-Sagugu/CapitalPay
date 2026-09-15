from rest_framework import serializers
from .models import AdjustmentApplication, AdjustmentApproval


class AdjustmentApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdjustmentApplication
        fields = "__all__"
        extra_kwargs = {
            "application_no": {"required": False},
            "applicant": {"required": False, "allow_blank": True},
            "status": {"required": False},
            "adjustment_amount": {"required": False},
        }


class AdjustmentApplicationListSerializer(serializers.ModelSerializer):
    last_approval_comment = serializers.CharField(read_only=True)
    last_approval_action = serializers.CharField(read_only=True)

    class Meta:
        model = AdjustmentApplication
        fields = [
            "id", "application_no", "diff_type", "status", "order_no",
            "bank_channel", "amount", "currency", "reason", "adjustment_amount",
            "applicant", "applied_at", "completed_at", "last_approval_comment",
            "last_approval_action", "remark"
        ]


class AdjustmentApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdjustmentApproval
        fields = "__all__"


class AdjustmentApprovalActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=AdjustmentApproval.Action.choices)
    comment = serializers.CharField(required=False, allow_blank=True, default="")
    approver = serializers.CharField(max_length=50)
    approver_id = serializers.CharField(max_length=64, required=False, allow_blank=True)
