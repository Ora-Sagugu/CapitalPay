"""财务报表 — 报表生成服务。"""
from datetime import date
from decimal import Decimal
from django.db.models import Sum, Count, Q
from apps.payment.models import PaymentOrder, RefundOrder
from apps.settlement.models import SettlementBatch, SettlementDetail
from apps.merchant.models import Merchant
from .models import MerchantDailyReport, ChannelFeeReport, PlatformOrderSummary


class ReportGenerator:
    """报表生成器。"""

    def generate_merchant_daily_report(self, report_date: date, merchant: Merchant = None):
        """生成商户日收单报表。"""
        merchants = [merchant] if merchant else Merchant.objects.filter(
            status=Merchant.Status.ACTIVE, is_deleted=False
        )

        reports = []
        for m in merchants:
            orders = PaymentOrder.objects.filter(
                merchant=m,
                pay_received_at__date=report_date,
                status__in=[
                    PaymentOrder.OrderStatus.PAY_RECEIVED,
                    PaymentOrder.OrderStatus.PENDING_SETTLE,
                    PaymentOrder.OrderStatus.SETTLED,
                ],
            )

            refunds = RefundOrder.objects.filter(
                payment_order__merchant=m,
                refunded_at__date=report_date,
                status=RefundOrder.RefundStatus.SUCCESS,
            )

            order_agg = orders.aggregate(
                count=Count("id"),
                total=Sum("amount"),
                fee=Sum("fee_amount"),
            )
            refund_agg = refunds.aggregate(
                count=Count("id"),
                total=Sum("refund_amount"),
            )

            report, _ = MerchantDailyReport.objects.update_or_create(
                report_date=report_date,
                merchant=m,
                defaults={
                    "total_orders": order_agg["count"] or 0,
                    "total_amount": order_agg["total"] or Decimal("0"),
                    "total_fee": order_agg["fee"] or Decimal("0"),
                    "total_refunds": refund_agg["count"] or 0,
                    "total_refund_amount": refund_agg["total"] or Decimal("0"),
                    "net_amount": (order_agg["total"] or Decimal("0")) - (refund_agg["total"] or Decimal("0")),
                },
            )
            reports.append(report)

        return reports

    def generate_channel_fee_report(self, report_date: date):
        """生成渠道手续费结算表。"""
        from apps.payment.gateway import BankGatewayRouter

        reports = []
        for bank in BankGatewayRouter.list_banks():
            bank_code = bank["bank_code"]

            orders = PaymentOrder.objects.filter(
                bank_code=bank_code,
                pay_received_at__date=report_date,
                status__in=[
                    PaymentOrder.OrderStatus.PAY_RECEIVED,
                    PaymentOrder.OrderStatus.PENDING_SETTLE,
                    PaymentOrder.OrderStatus.SETTLED,
                ],
            )

            agg = orders.aggregate(
                count=Count("id"),
                total=Sum("amount"),
                fee=Sum("fee_amount"),
            )

            report, _ = ChannelFeeReport.objects.update_or_create(
                report_date=report_date,
                bank_code=bank_code,
                defaults={
                    "bank_name": bank["bank_name"],
                    "total_orders": agg["count"] or 0,
                    "total_amount": agg["total"] or Decimal("0"),
                    "channel_fee": (agg["total"] or Decimal("0")) * Decimal("0.003"),
                    "platform_fee": (agg["fee"] or Decimal("0")) - (agg["total"] or Decimal("0")) * Decimal("0.003"),
                },
            )
            reports.append(report)

        return reports

    def generate_platform_summary(self, report_date: date):
        """生成平台订单汇总表。"""
        orders = PaymentOrder.objects.filter(
            pay_received_at__date=report_date,
            status__in=[
                PaymentOrder.OrderStatus.PAY_RECEIVED,
                PaymentOrder.OrderStatus.PENDING_SETTLE,
                PaymentOrder.OrderStatus.SETTLED,
            ],
        )
        refunds = RefundOrder.objects.filter(
            refunded_at__date=report_date,
            status=RefundOrder.RefundStatus.SUCCESS,
        )
        settlements = SettlementBatch.objects.filter(
            settle_date=report_date,
            status=SettlementBatch.SettleStatus.SETTLED,
        )

        order_agg = orders.aggregate(
            count=Count("id"), total=Sum("amount"), fee=Sum("fee_amount")
        )
        refund_agg = refunds.aggregate(count=Count("id"), total=Sum("refund_amount"))
        settle_agg = settlements.aggregate(total=Sum("settle_net_amount"))
        merchants_count = orders.values("merchant").distinct().count()

        summary, _ = PlatformOrderSummary.objects.update_or_create(
            report_date=report_date,
            defaults={
                "total_merchants": merchants_count,
                "total_orders": order_agg["count"] or 0,
                "total_amount": order_agg["total"] or Decimal("0"),
                "total_fee": order_agg["fee"] or Decimal("0"),
                "total_refunds": refund_agg["count"] or 0,
                "total_refund_amount": refund_agg["total"] or Decimal("0"),
                "settled_amount": settle_agg["total"] or Decimal("0"),
            },
        )
        return summary
