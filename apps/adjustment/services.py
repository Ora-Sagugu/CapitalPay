import uuid
from typing import Optional, Dict, Any
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.utils import timezone
from .models import AdjustmentApplication, AdjustmentApproval


class AdjustmentService:
    """差异账调账服务"""

    @staticmethod
    def generate_application_no() -> str:
        from datetime import datetime
        return f"ADJ{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"

    @staticmethod
    def list_applications(
        status: Optional[str] = None,
        diff_type: Optional[str] = None,
        order_no: Optional[str] = None,
        applicant: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        queryset = AdjustmentApplication.objects.prefetch_related("approvals")
        if status:
            queryset = queryset.filter(status=status)
        if diff_type:
            queryset = queryset.filter(diff_type=diff_type)
        if order_no:
            queryset = queryset.filter(order_no__icontains=order_no)
        if applicant:
            queryset = queryset.filter(Q(applicant__icontains=applicant))
        if start_date:
            queryset = queryset.filter(applied_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(applied_at__lte=end_date)
        total = queryset.count()
        paginator = Paginator(queryset.order_by("-applied_at"), page_size)
        page_obj = paginator.get_page(page)
        results = []
        for app in page_obj.object_list:
            last_approval = app.approvals.order_by("-approved_at").first()
            results.append({
                "id": str(app.id),
                "application_no": app.application_no,
                "diff_type": app.diff_type,
                "status": app.status,
                "order_no": app.order_no,
                "bank_channel": app.bank_channel,
                "amount": str(app.amount),
                "currency": app.currency,
                "reason": app.reason,
                "adjustment_amount": str(app.adjustment_amount),
                "applicant": app.applicant,
                "applied_at": app.applied_at.isoformat(),
                "completed_at": app.completed_at.isoformat() if app.completed_at else None,
                "last_approval_comment": last_approval.comment if last_approval else None,
                "last_approval_action": last_approval.action if last_approval else None,
                "remark": app.remark
            })
        # 统计
        stats = {
            "total": queryset.count(),
            "pending": queryset.filter(status=AdjustmentApplication.Status.PENDING).count(),
            "approved": queryset.filter(status=AdjustmentApplication.Status.APPROVED).count(),
            "rejected": queryset.filter(status=AdjustmentApplication.Status.REJECTED).count(),
            "total_adjustment_amount": str(queryset.filter(status=AdjustmentApplication.Status.APPROVED).aggregate(
                total=Sum("adjustment_amount")
            )["total"] or 0)
        }
        return {
            "total": total, "page": page, "page_size": page_size,
            "results": results, "stats": stats
        }

    @staticmethod
    def create_application(data: Dict[str, Any]) -> AdjustmentApplication:
        from uuid import uuid4
        data["application_no"] = f"ADJ{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid4().hex[:4].upper()}"
        app = AdjustmentApplication.objects.create(**data)
        return app

    @staticmethod
    def get_application(app_id: str) -> Optional[AdjustmentApplication]:
        try:
            return AdjustmentApplication.objects.prefetch_related("approvals").get(id=app_id)
        except AdjustmentApplication.DoesNotExist:
            return None

    @staticmethod
    def approve_application(app_id: str, approver: str, approver_id: str, comment: str = "") -> Optional[AdjustmentApplication]:
        try:
            app = AdjustmentApplication.objects.get(id=app_id)
            if app.status != AdjustmentApplication.Status.PENDING:
                return None
            AdjustmentApproval.objects.create(
                application=app, approver=approver, approver_id=approver_id,
                action=AdjustmentApproval.Action.APPROVE, comment=comment
            )
            app.status = AdjustmentApplication.Status.APPROVED
            app.completed_at = timezone.now()
            app.save()
            return app
        except AdjustmentApplication.DoesNotExist:
            return None

    @staticmethod
    def reject_application(app_id: str, approver: str, approver_id: str, comment: str = "") -> Optional[AdjustmentApplication]:
        try:
            app = AdjustmentApplication.objects.get(id=app_id)
            if app.status != AdjustmentApplication.Status.PENDING:
                return None
            AdjustmentApproval.objects.create(
                application=app, approver=approver, approver_id=approver_id,
                action=AdjustmentApproval.Action.REJECT, comment=comment
            )
            app.status = AdjustmentApplication.Status.REJECTED
            app.completed_at = timezone.now()
            app.save()
            return app
        except AdjustmentApplication.DoesNotExist:
            return None

    @staticmethod
    def cancel_application(app_id: str) -> bool:
        try:
            app = AdjustmentApplication.objects.get(id=app_id)
            if app.status not in (AdjustmentApplication.Status.PENDING,):
                return False
            app.status = AdjustmentApplication.Status.CANCELLED
            app.save()
            return True
        except AdjustmentApplication.DoesNotExist:
            return False
