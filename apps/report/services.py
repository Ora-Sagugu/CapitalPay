"""财务报表 — 报表生成服务。"""
from datetime import date
from decimal import Decimal
from django.db.models import Sum, Count
from django.utils import timezone
from apps.payment.models import PaymentOrder, RefundOrder
from apps.settlement.models import SettlementBatch
from apps.merchant.models import Merchant
from apps.param.services import resolve_channel_rate
from .models import MerchantDailyReport, ChannelFeeReport, PlatformOrderSummary


RECEIVED_STATUSES = [
    PaymentOrder.OrderStatus.PAY_RECEIVED,
    PaymentOrder.OrderStatus.PENDING_SETTLE,
    PaymentOrder.OrderStatus.SETTLED,
    PaymentOrder.OrderStatus.COMPLETED,
]


class ReportGenerator:
    """报表生成器 — 按币种拆分，幂等重算。"""

    def generate_merchant_daily_report(self, report_date: date, merchant: Merchant = None):
        """生成商户日收单报表。"""
        merchants = [merchant] if merchant else list(Merchant.objects.filter(
            status=Merchant.Status.ACTIVE, is_deleted=False
        ))
        watermark = timezone.now()
        reports = []
        for m in merchants:
            orders = PaymentOrder.objects.filter(
                merchant=m,
                is_deleted=False,
                pay_received_at__date=report_date,
                status__in=RECEIVED_STATUSES,
            )
            currencies = list(
                orders.values_list("from_currency", flat=True).distinct()
            ) or [""]
            for currency in currencies:
                scoped = orders.filter(from_currency=currency) if currency else orders
                refunds = RefundOrder.objects.filter(
                    payment_order__merchant=m,
                    payment_order__from_currency=currency or "",
                    refunded_at__date=report_date,
                    status=RefundOrder.RefundStatus.SUCCESS,
                    is_deleted=False,
                )
                order_agg = scoped.aggregate(
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
                    currency=currency or "",
                    defaults={
                        "total_orders": order_agg["count"] or 0,
                        "total_amount": order_agg["total"] or Decimal("0"),
                        "total_fee": order_agg["fee"] or Decimal("0"),
                        "total_refunds": refund_agg["count"] or 0,
                        "total_refund_amount": refund_agg["total"] or Decimal("0"),
                        "net_amount": (order_agg["total"] or Decimal("0")) - (refund_agg["total"] or Decimal("0")),
                        "data_watermark": watermark,
                    },
                )
                reports.append(report)
        return reports

    def generate_channel_fee_report(self, report_date: date):
        """生成渠道手续费结算表。"""
        from apps.payment.gateway import BankGatewayRouter

        watermark = timezone.now()
        reports = []
        for bank in BankGatewayRouter.list_banks():
            bank_code = bank["bank_code"]
            orders = PaymentOrder.objects.filter(
                bank_code=bank_code,
                is_deleted=False,
                pay_received_at__date=report_date,
                status__in=RECEIVED_STATUSES,
            )
            currencies = list(orders.values_list("from_currency", flat=True).distinct()) or [""]
            for currency in currencies:
                scoped = orders.filter(from_currency=currency) if currency else orders
                agg = scoped.aggregate(
                    count=Count("id"),
                    total=Sum("amount"),
                    fee=Sum("fee_amount"),
                )
                total = agg["total"] or Decimal("0")
                fee = agg["fee"] or Decimal("0")
                channel_fee = total * resolve_channel_rate(bank_code)
                report, _ = ChannelFeeReport.objects.update_or_create(
                    report_date=report_date,
                    bank_code=bank_code,
                    currency=currency or "",
                    defaults={
                        "bank_name": bank["bank_name"],
                        "total_orders": agg["count"] or 0,
                        "total_amount": total,
                        "channel_fee": channel_fee,
                        "platform_fee": fee - channel_fee,
                        "data_watermark": watermark,
                    },
                )
                reports.append(report)
        return reports

    def generate_platform_summary(self, report_date: date):
        """生成平台订单汇总表（按币种一行）。"""
        watermark = timezone.now()
        orders = PaymentOrder.objects.filter(
            is_deleted=False,
            pay_received_at__date=report_date,
            status__in=RECEIVED_STATUSES,
        )
        currencies = list(orders.values_list("from_currency", flat=True).distinct()) or [""]
        summaries = []
        for currency in currencies:
            scoped = orders.filter(from_currency=currency) if currency else orders
            refunds = RefundOrder.objects.filter(
                is_deleted=False,
                refunded_at__date=report_date,
                status=RefundOrder.RefundStatus.SUCCESS,
                payment_order__from_currency=currency or "",
            )
            settlements = SettlementBatch.objects.filter(
                settle_date=report_date,
                status=SettlementBatch.SettleStatus.SETTLED,
                is_deleted=False,
                currency=currency or "",
            )
            order_agg = scoped.aggregate(
                count=Count("id"), total=Sum("amount"), fee=Sum("fee_amount")
            )
            refund_agg = refunds.aggregate(count=Count("id"), total=Sum("refund_amount"))
            settle_agg = settlements.aggregate(total=Sum("settle_net_amount"))
            merchants_count = scoped.values("merchant").distinct().count()
            summary, _ = PlatformOrderSummary.objects.update_or_create(
                report_date=report_date,
                currency=currency or "",
                defaults={
                    "total_merchants": merchants_count,
                    "total_orders": order_agg["count"] or 0,
                    "total_amount": order_agg["total"] or Decimal("0"),
                    "total_fee": order_agg["fee"] or Decimal("0"),
                    "total_refunds": refund_agg["count"] or 0,
                    "total_refund_amount": refund_agg["total"] or Decimal("0"),
                    "settled_amount": settle_agg["total"] or Decimal("0"),
                    "data_watermark": watermark,
                },
            )
            summaries.append(summary)
        return summaries[0] if len(summaries) == 1 else summaries

    def generate_all(self, report_date: date):
        daily = self.generate_merchant_daily_report(report_date)
        channel = self.generate_channel_fee_report(report_date)
        summary = self.generate_platform_summary(report_date)
        summary_count = 1 if summary and not isinstance(summary, list) else len(summary or [])
        return {
            "merchant_daily": len(daily),
            "channel_fee": len(channel),
            "platform_summary": summary_count,
        }
