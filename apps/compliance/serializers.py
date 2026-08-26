"""Compliance serializers"""
from rest_framework import serializers
from .models import SanctionList, SanctionScanRecord, SanctionHitDetail


class SanctionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = SanctionList
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class SanctionHitDetailSerializer(serializers.ModelSerializer):
    entity_name = serializers.CharField(source="sanction_entry.entity_name", read_only=True)
    risk_level = serializers.CharField(source="sanction_entry.risk_level", read_only=True)
    list_type = serializers.CharField(source="sanction_entry.get_list_type_display", read_only=True)

    class Meta:
        model = SanctionHitDetail
        fields = "__all__"


class SanctionScanRecordSerializer(serializers.ModelSerializer):
    hits = SanctionHitDetailSerializer(many=True, read_only=True)

    class Meta:
        model = SanctionScanRecord
        fields = "__all__"
        read_only_fields = ["scan_no", "created_at", "updated_at"]
