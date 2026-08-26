from typing import Optional
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .services import AdjustmentService
from .serializers import (
    AdjustmentApplicationSerializer, AdjustmentApplicationListSerializer,
    AdjustmentApprovalSerializer, AdjustmentApprovalActionSerializer
)
from .models import AdjustmentApplication, AdjustmentApproval


class AdjustmentApplicationViewSet(viewsets.ViewSet):
    """差异账调账申请管理"""
    permission_classes = [AllowAny]

    def list(self, request):
        status_param = request.query_params.get("status")
        diff_type = request.query_params.get("diff_type")
        order_no = request.query_params.get("order_no")
        applicant = request.query_params.get("applicant")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        data = AdjustmentService.list_applications(
            status_param, diff_type, order_no, applicant, start_date, end_date, page, page_size
        )
        return Response(data)

    def create(self, request):
        ser = AdjustmentApplicationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        app = AdjustmentService.create_application(ser.validated_data)
        return Response(AdjustmentApplicationSerializer(app).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        try:
            app = AdjustmentApplication.objects.prefetch_related("approvals").get(id=pk)
            data = AdjustmentApplicationSerializer(app).data
            data["approvals"] = AdjustmentApprovalSerializer(
                app.approvals.order_by("-approved_at"), many=True
            ).data
            return Response(data)
        except AdjustmentApplication.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    def update(self, request, pk=None):
        try:
            app = AdjustmentApplication.objects.get(id=pk)
            if app.status != AdjustmentApplication.Status.PENDING:
                return Response({"detail": "Can only update pending applications"}, status=status.HTTP_400_BAD_REQUEST)
            ser = AdjustmentApplicationSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            for key, value in ser.validated_data.items():
                if hasattr(app, key):
                    setattr(app, key, value)
            app.save()
            return Response(AdjustmentApplicationSerializer(app).data)
        except AdjustmentApplication.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, pk=None):
        try:
            app = AdjustmentApplication.objects.get(id=pk)
            if app.status not in (AdjustmentApplication.Status.PENDING, AdjustmentApplication.Status.CANCELLED):
                return Response({"detail": "Can only delete pending or cancelled applications"}, status=status.HTTP_400_BAD_REQUEST)
            app.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except AdjustmentApplication.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        data = {**request.data}
        data.setdefault("action", "approve")
        data.setdefault("approver", getattr(request.user, "username", None) or "admin")
        data.setdefault("comment", "")
        ser = AdjustmentApprovalActionSerializer(data=data)
        ser.is_valid(raise_exception=True)
        action = ser.validated_data["action"]
        if action == "approve":
            app = AdjustmentService.approve_application(
                pk, ser.validated_data["approver"], ser.validated_data.get("approver_id", ""), ser.validated_data["comment"]
            )
        else:
            app = AdjustmentService.reject_application(
                pk, ser.validated_data["approver"], ser.validated_data.get("approver_id", ""), ser.validated_data["comment"]
            )
        if app:
            return Response(AdjustmentApplicationSerializer(app).data)
        return Response({"detail": "Not found or not pending"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """拒绝调账申请。"""
        data = {**request.data}
        data["action"] = "reject"
        data.setdefault("approver", getattr(request.user, "username", None) or "admin")
        data.setdefault("comment", data.get("comment") or data.get("reason") or "拒绝")
        ser = AdjustmentApprovalActionSerializer(data=data)
        ser.is_valid(raise_exception=True)
        app = AdjustmentService.reject_application(
            pk,
            ser.validated_data["approver"],
            ser.validated_data.get("approver_id", ""),
            ser.validated_data["comment"],
        )
        if app:
            return Response(AdjustmentApplicationSerializer(app).data)
        return Response({"detail": "Not found or not pending"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        if AdjustmentService.cancel_application(pk):
            return Response({"detail": "Cancelled"})
        return Response({"detail": "Not found or not pending"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        from django.db.models import Sum, Count
        stats = {
            "total": AdjustmentApplication.objects.count(),
            "pending": AdjustmentApplication.objects.filter(status=AdjustmentApplication.Status.PENDING).count(),
            "approved": AdjustmentApplication.objects.filter(status=AdjustmentApplication.Status.APPROVED).count(),
            "rejected": AdjustmentApplication.objects.filter(status=AdjustmentApplication.Status.REJECTED).count(),
            "total_adjustment_amount": str(AdjustmentApplication.objects.filter(
                status=AdjustmentApplication.Status.APPROVED
            ).aggregate(total=Sum("adjustment_amount"))["total"] or 0)
        }
        return Response(stats)
