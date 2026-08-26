"""Core API views — Dashboard"""
from rest_framework import views, status
from rest_framework.response import Response
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta

from apps.rbac.authentication import JWTAuthentication
from apps.merchant.models import Merchant
from apps.payment.models import PaymentOrder
from apps.agent.models import Agent


class DashboardView(views.APIView):
    """工作台 Dashboard API"""
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        today = timezone.now().date()
        today_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
        today_end = today_start + timedelta(days=1)

        # 今日汇款
        today_orders = PaymentOrder.objects.filter(
            is_deleted=False,
            pay_received_at__gte=today_start,
            pay_received_at__lt=today_end,
            status__in=["PAY_RECEIVED", "PENDING_SETTLE", "SETTLED"],
        )
        today_count = today_orders.count()
        today_amount = today_orders.aggregate(total=Sum("amount"))["total"] or 0

        # 待处理
        pending_orders = PaymentOrder.objects.filter(
            is_deleted=False,
            status="PENDING_PAY",
        )
        pending_count = pending_orders.count()

        # 审核中/通过
        reviewing_count = PaymentOrder.objects.filter(
            is_deleted=False,
            status="PAY_RECEIVED",
        ).count()

        # 已完成
        completed_count = PaymentOrder.objects.filter(
            is_deleted=False,
            status__in=["SETTLED", "PENDING_SETTLE"],
        ).count()
        transferred_count = PaymentOrder.objects.filter(
            is_deleted=False,
            status="SETTLED",
        ).count()

        # 失败
        failed_count = PaymentOrder.objects.filter(
            is_deleted=False,
            status="CLOSED",
        ).count()
        from apps.payment.models import RefundOrder
        refund_count = RefundOrder.objects.filter(status="REJECTED").count()
        cancelled_count = PaymentOrder.objects.filter(
            is_deleted=False,
            status="CLOSED",
        ).count()

        # 客户总数
        customer_count = Merchant.objects.filter(is_deleted=False).count()

        # 代理总数
        agent_count = Agent.objects.filter(is_deleted=False).count()

        # 汇款总笔数
        total_orders = PaymentOrder.objects.filter(is_deleted=False).count()

        # 每日汇款额趋势 (最近7天)
        trend_data = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_start = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()))
            day_end = day_start + timedelta(days=1)
            day_orders = PaymentOrder.objects.filter(
                is_deleted=False,
                pay_received_at__gte=day_start,
                pay_received_at__lt=day_end,
            )
            day_total = day_orders.aggregate(total=Sum("amount"))["total"] or 0
            trend_data.append({
                "date": day.strftime("%m-%d"),
                "amount": float(day_total),
                "count": day_orders.count(),
            })

        return Response({
            "today_remittance": {
                "count": today_count,
                "amount": float(today_amount),
            },
            "pending": {
                "count": pending_count,
                "reviewing": reviewing_count,
                "approved": 0,  # from RefundOrder approved
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
