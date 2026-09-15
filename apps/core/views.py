"""Core API views — Dashboard"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum, Value
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone
from django.utils.timezone import get_current_timezone
from rest_framework import views
from rest_framework.response import Response

from apps.agent.models import Agent
from apps.merchant.models import Merchant
from apps.payment.models import PaymentOrder
from apps.rbac.authentication import JWTAuthentication
from apps.rbac.permissions import RequiresFeature


class DashboardView(RequiresFeature, views.APIView):
    """工作台 Dashboard API"""
    authentication_classes = [JWTAuthentication]
    feature_code = "feature:dashboard"

    def get(self, request):
        today = timezone.localdate()
        tz = get_current_timezone()
        today_start = timezone.make_aware(
            timezone.datetime.combine(today, timezone.datetime.min.time()), tz
        )
        today_end = today_start + timedelta(days=1)

        today_orders = PaymentOrder.objects.filter(
            is_deleted=False,
            created_at__gte=today_start,
            created_at__lt=today_end,
        )
        today_count = today_orders.count()
        today_amount = today_orders.aggregate(total=Sum("amount"))["total"] or 0

        pending_orders = PaymentOrder.objects.filter(
            is_deleted=False,
            status__in=["PENDING_REVIEW", "PENDING_PAY"],
        )
        pending_count = pending_orders.count()

        reviewing_count = PaymentOrder.objects.filter(
            is_deleted=False,
            status="PAY_RECEIVED",
        ).count()

        completed_count = PaymentOrder.objects.filter(
            is_deleted=False,
            status__in=["SETTLED", "PENDING_SETTLE", "COMPLETED"],
        ).count()
        transferred_count = PaymentOrder.objects.filter(
            is_deleted=False,
            status="SETTLED",
        ).count()

        failed_count = PaymentOrder.objects.filter(
            is_deleted=False,
            status="CLOSED",
        ).count()
        from apps.payment.models import RefundOrder
        refund_count = RefundOrder.objects.filter(status="REJECTED").count()
        cancelled_count = failed_count

        customer_count = Merchant.objects.filter(is_deleted=False).count()
        agent_count = Agent.objects.filter(is_deleted=False).count()
        total_orders = PaymentOrder.objects.filter(is_deleted=False).count()

        range_key = (request.query_params.get("range") or "7d").lower()
        range_days = {"7d": 7, "1m": 30, "3m": 90, "6m": 180}.get(range_key, 7)
        range_start = today_start - timedelta(days=range_days - 1)
        grouped = (
            PaymentOrder.objects.filter(
                is_deleted=False,
                created_at__gte=range_start,
                created_at__lt=today_end,
            )
            .annotate(day=TruncDate("created_at", tzinfo=tz))
            .values("day")
            .annotate(
                count=Count("id"),
                amount=Coalesce(Sum("amount"), Value(Decimal("0.00"))),
            )
        )
        by_day = {
            (row["day"].isoformat() if hasattr(row["day"], "isoformat") else str(row["day"])): row
            for row in grouped if row["day"]
        }
        trend_data = []
        for i in range(range_days - 1, -1, -1):
            day = today - timedelta(days=i)
            row = by_day.get(day.isoformat()) or {}
            trend_data.append({
                "date": day.strftime("%m-%d"),
                "amount": float(row.get("amount") or 0),
                "count": row.get("count") or 0,
            })

        return Response({
            "today_date": today.isoformat(),
            "today_remittance": {
                "count": today_count,
                "amount": float(today_amount),
            },
            "pending": {
                "count": pending_count,
                "reviewing": reviewing_count,
                "approved": 0,
            },
            "completed": {
                "count": completed_count,
                "transferred": transferred_count,
                "finished": completed_count,
            },
            "failed": {
                "count": failed_count,
                "refused": refund_count,
                "refunded": refund_count,
                "cancelled": cancelled_count,
            },
            "customers_total": customer_count,
            "agents_total": agent_count,
            "orders_total": total_orders,
            "trend": trend_data,
        })
