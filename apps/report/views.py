"""财务报表 — API Views (运营管理端)。"""
from datetime import datetime

from django.http import HttpResponse
from django.utils.timezone import make_aware
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from apps.payment.models import PaymentOrder
from apps.merchant.models import Merchant
from apps.agent.models import Agent
from .models import MerchantDailyReport, ChannelFeeReport, PlatformOrderSummary
from .serializers import (
    MerchantDailyReportSerializer, ChannelFeeReportSerializer,
    PlatformOrderSummarySerializer, SettlementBatchReportSerializer,
)
from apps.settlement.models import SettlementBatch, SettlementDetail


STATUS_LABEL_MAP = {
    "PRE_CREATE": "Pre-created",
    "PENDING_REVIEW": "Pending Review",
    "PROCESSING": "Processing",
    "COMPLETED": "Completed",
    "PENDING_PAY": "Pending Payment",
    "PAY_RECEIVED": "Payment Received",
    "PENDING_SETTLE": "Pending Settlement",
    "SETTLED": "Settled",
    "CLOSED": "Closed",
    "REFUNDING": "Refunding",
    "REFUNDED": "Refunded",
}
FEE_BEARING_MAP = {"OUR": "Sender Pays", "SHA": "Shared", "BEN": "Beneficiary Pays"}
PAY_METHOD_LABEL_MAP = dict(PaymentOrder.PayMethod.choices)


class RemittanceReportViewSet(viewsets.ViewSet):
    """汇款业务报表 — 查询 & 导出。"""

    @action(detail=False, methods=["post"], url_path="query")
    def query_remittance(self, request):
        """查询汇款业务数据（预览）。支持按代理商或按客户筛选。"""
        merchant_id = request.data.get("merchant_id")
        agent_id = request.data.get("agent_id")
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")

        if not all([start_date, end_date]):
            return Response({"error": "Please select start and end dates"}, status=400)
        if not merchant_id and not agent_id:
            return Response({"error": "Please select an agent or customer"}, status=400)

        try:
            start_dt = make_aware(datetime.strptime(start_date, "%Y-%m-%d"))
            end_dt = make_aware(datetime.strptime(end_date, "%Y-%m-%d")).replace(hour=23, minute=59, second=59)
        except ValueError:
            return Response({"error": "Invalid date format"}, status=400)

        # 按代理商查询：汇总该代理商下所有商户的订单
        if agent_id and not merchant_id:
            merchant_ids = list(Merchant.objects.filter(
                agent_id=agent_id, is_deleted=False
            ).values_list("id", flat=True))
            if not merchant_ids:
                return Response({
                    "query_type": "agent", "agent_name": "", "merchant_name": "",
                    "total_count": 0, "total_amount": 0, "total_fee": 0, "orders": [],
                })
            orders = PaymentOrder.objects.filter(
                merchant_id__in=merchant_ids,
                pay_method=PaymentOrder.PayMethod.WIRE_TRANSFER,
                created_at__range=(start_dt, end_dt),
                is_deleted=False,
            ).select_related("merchant").order_by("-created_at")
            try:
                agent_name = Agent.objects.get(id=agent_id).agent_name
            except Agent.DoesNotExist:
                agent_name = ""
            query_label = agent_name
            query_type = "agent"
        else:
            # 按单个客户查询
            orders = PaymentOrder.objects.filter(
                merchant_id=merchant_id,
                pay_method=PaymentOrder.PayMethod.WIRE_TRANSFER,
                created_at__range=(start_dt, end_dt),
                is_deleted=False,
            ).select_related("merchant").order_by("-created_at")
            query_label = ""
            if orders:
                query_label = orders[0].merchant.merchant_name
            else:
                try:
                    query_label = Merchant.objects.get(id=merchant_id).merchant_name
                except Merchant.DoesNotExist:
                    pass
            query_type = "merchant"
            agent_name = ""

        results = []
        total_amount = 0
        total_fee = 0
        for order in orders:
            results.append({
                "order_no": order.order_no,
                "merchant_order_no": order.merchant_order_no,
                "prn_code": order.prn_code or "",
                "merchant_name": order.merchant.merchant_name,
                "beneficiary_name": order.beneficiary_name,
                "beneficiary_bank": order.beneficiary_bank,
                "beneficiary_swift": order.beneficiary_swift,
                "beneficiary_account": order.beneficiary_account,
                "beneficiary_address": order.beneficiary_address,
                "remittance_purpose": order.remittance_purpose,
                "from_currency": order.from_currency,
                "to_currency": order.to_currency,
                "amount": str(order.amount),
                "fee_amount": str(order.fee_amount),
                "fee_bearing": order.fee_bearing,
                "fee_bearing_label": FEE_BEARING_MAP.get(order.fee_bearing, order.fee_bearing),
                "status": order.status,
                "status_label": STATUS_LABEL_MAP.get(order.status, order.status),
                "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S") if order.created_at else "",
                "pay_received_at": order.pay_received_at.strftime("%Y-%m-%d %H:%M:%S") if order.pay_received_at else "",
            })
            total_amount += float(order.amount)
            total_fee += float(order.fee_amount)

        response_data = {
            "query_type": query_type,
            "merchant_name": query_label if query_type == "merchant" else "",
            "agent_name": agent_name,
            "total_count": len(results),
            "total_amount": round(total_amount, 2),
            "total_fee": round(total_fee, 2),
            "orders": results,
        }
        if query_type == "agent":
            response_data["merchant_name"] = f"{agent_name} ({len(merchant_ids)} merchants)"
        return Response(response_data)

    @action(detail=False, methods=["post"], url_path="export")
    def export_remittance(self, request):
        """导出汇款业务数据为 Excel。支持按代理商或按客户筛选。"""
        merchant_id = request.data.get("merchant_id")
        agent_id = request.data.get("agent_id")
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")

        if not all([start_date, end_date]):
            return Response({"error": "Please select start and end dates"}, status=400)
        if not merchant_id and not agent_id:
            return Response({"error": "Please select an agent or customer"}, status=400)

        try:
            start_dt = make_aware(datetime.strptime(start_date, "%Y-%m-%d"))
            end_dt = make_aware(datetime.strptime(end_date, "%Y-%m-%d")).replace(hour=23, minute=59, second=59)
        except ValueError:
            return Response({"error": "Invalid date format"}, status=400)

        # 按代理商查询：汇总该代理商下所有商户的订单
        if agent_id and not merchant_id:
            merchant_ids = list(Merchant.objects.filter(
                agent_id=agent_id, is_deleted=False
            ).values_list("id", flat=True))
            orders = PaymentOrder.objects.filter(
                merchant_id__in=merchant_ids,
                pay_method=PaymentOrder.PayMethod.WIRE_TRANSFER,
                created_at__range=(start_dt, end_dt),
                is_deleted=False,
            ).select_related("merchant").order_by("-created_at")
            try:
                agent_name = Agent.objects.get(id=agent_id).agent_name
            except Agent.DoesNotExist:
                agent_name = "Unknown Agent"
            query_label = agent_name
        else:
            orders = PaymentOrder.objects.filter(
                merchant_id=merchant_id,
                pay_method=PaymentOrder.PayMethod.WIRE_TRANSFER,
                created_at__range=(start_dt, end_dt),
                is_deleted=False,
            ).select_related("merchant").order_by("-created_at")
            query_label = ""
            if orders:
                query_label = orders[0].merchant.merchant_name
            else:
                try:
                    query_label = Merchant.objects.get(id=merchant_id).merchant_name
                except Merchant.DoesNotExist:
                    query_label = "Unknown Customer"

        # 生成 Excel
        import openpyxl
        from openpyxl.styles import Font, Alignment, Border, Side, PatternFill, numbers
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Remittance Report"

        # ── Title Row ──
        title_font = Font(name="Arial", size=14, bold=True, color="1F2937")
        subtitle_font = Font(name="Arial", size=10, color="6B7280")
        header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="3B82F6", end_color="3B82F6", fill_type="solid")
        data_font = Font(name="Arial", size=10, color="374151")
        thin_border = Border(
            left=Side(style="thin", color="D1D5DB"),
            right=Side(style="thin", color="D1D5DB"),
            top=Side(style="thin", color="D1D5DB"),
            bottom=Side(style="thin", color="D1D5DB"),
        )
        center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)

        # Row 1: Report title
        is_agent_export = bool(agent_id and not merchant_id)
        merge_range = "A1:S1" if is_agent_export else "A1:R1"
        ws.merge_cells(merge_range)
        ws["A1"] = f"Remittance Report — {query_label}"
        ws["A1"].font = title_font
        ws["A1"].alignment = center_align

        # Row 2: Date range & summary
        merge_range2 = "A2:S2" if is_agent_export else "A2:R2"
        ws.merge_cells(merge_range2)
        total_amount = sum(float(o.amount) for o in orders)
        total_fee = sum(float(o.fee_amount) for o in orders)
        ws["A2"] = f"Period: {start_date} ~ {end_date}  |  Total: {len(orders)} orders  |  Amount: ${total_amount:,.2f}  |  Fees: ${total_fee:,.2f}"
        ws["A2"].font = subtitle_font
        ws["A2"].alignment = center_align

        # Row 4: Headers
        if is_agent_export:
            headers = [
                "No.", "Order No.", "Merchant Order No.", "PRN Code", "Merchant", "Beneficiary Name", "Beneficiary Bank",
                "SWIFT", "Beneficiary Account", "Beneficiary Address", "Remittance Purpose",
                "Source Currency", "Target Currency", "Amount", "Fee", "Fee Bearer",
                "Status", "Created At", "Received At",
            ]
            col_widths = [6, 28, 22, 10, 16, 16, 20, 14, 20, 24, 24, 10, 10, 14, 12, 12, 12, 20, 20]
        else:
            headers = [
                "No.", "Order No.", "Merchant Order No.", "PRN Code", "Beneficiary Name", "Beneficiary Bank",
                "SWIFT", "Beneficiary Account", "Beneficiary Address", "Remittance Purpose",
                "Source Currency", "Target Currency", "Amount", "Fee", "Fee Bearer",
                "Status", "Created At", "Received At",
            ]
            col_widths = [6, 28, 22, 10, 16, 20, 14, 20, 24, 24, 10, 10, 14, 12, 12, 12, 20, 20]
        header_row = 4
        for col_idx, (header, width) in enumerate(zip(headers, col_widths), 1):
            cell = ws.cell(row=header_row, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = thin_border
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        # 数据行
        for idx, order in enumerate(orders, 1):
            row = header_row + idx
            if is_agent_export:
                row_data = [
                    idx,
                    order.order_no,
                    order.merchant_order_no,
                    order.prn_code or "",
                    order.merchant.merchant_name,
                    order.beneficiary_name,
                    order.beneficiary_bank,
                    order.beneficiary_swift,
                    order.beneficiary_account,
                    order.beneficiary_address,
                    order.remittance_purpose,
                    order.from_currency,
                    order.to_currency,
                    float(order.amount),
                    float(order.fee_amount),
                    FEE_BEARING_MAP.get(order.fee_bearing, order.fee_bearing),
                    STATUS_LABEL_MAP.get(order.status, order.status),
                    order.created_at.strftime("%Y-%m-%d %H:%M:%S") if order.created_at else "",
                    order.pay_received_at.strftime("%Y-%m-%d %H:%M:%S") if order.pay_received_at else "",
                ]
                center_cols = (1, 12, 13, 15, 16, 17)
                amount_col = 14
                fee_col = 15
            else:
                row_data = [
                    idx,
                    order.order_no,
                    order.merchant_order_no,
                    order.prn_code or "",
                    order.beneficiary_name,
                    order.beneficiary_bank,
                    order.beneficiary_swift,
                    order.beneficiary_account,
                    order.beneficiary_address,
                    order.remittance_purpose,
                    order.from_currency,
                    order.to_currency,
                    float(order.amount),
                    float(order.fee_amount),
                    FEE_BEARING_MAP.get(order.fee_bearing, order.fee_bearing),
                    STATUS_LABEL_MAP.get(order.status, order.status),
                    order.created_at.strftime("%Y-%m-%d %H:%M:%S") if order.created_at else "",
                    order.pay_received_at.strftime("%Y-%m-%d %H:%M:%S") if order.pay_received_at else "",
                ]
                center_cols = (1, 11, 12, 14, 15, 16)
                amount_col = 13
                fee_col = 14
            for col_idx, value in enumerate(row_data, 1):
                cell = ws.cell(row=row, column=col_idx, value=value)
                cell.font = data_font
                cell.border = thin_border
                if col_idx in center_cols:
                    cell.alignment = center_align
                else:
                    cell.alignment = left_align

            # 金额格式
            ws.cell(row=row, column=amount_col).number_format = '#,##0.00'
            ws.cell(row=row, column=fee_col).number_format = '#,##0.00'

            # 条纹行
            if idx % 2 == 0:
                stripe_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
                for col_idx in range(1, len(headers) + 1):
                    ws.cell(row=row, column=col_idx).fill = stripe_fill

        # 冻结表头
        ws.freeze_panes = f"A{header_row + 1}"

        # 返回文件
        filename = f"汇款业务报表_{query_label}_{start_date}_{end_date}.xlsx"
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response


class MerchantDailyReportViewSet(viewsets.ReadOnlyModelViewSet):
    """商户日收单报表。"""
    queryset = MerchantDailyReport.objects.filter(is_deleted=False).select_related("merchant", "merchant__agent")
    serializer_class = MerchantDailyReportSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["report_date", "merchant__merchant_no", "merchant__agent__agent_no"]
    ordering_fields = ["report_date", "total_amount"]


class ChannelFeeReportViewSet(viewsets.ReadOnlyModelViewSet):
    """渠道手续费结算表。"""
    queryset = ChannelFeeReport.objects.filter(is_deleted=False)
    serializer_class = ChannelFeeReportSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["report_date", "bank_code"]
    ordering_fields = ["report_date"]


class PlatformOrderSummaryViewSet(viewsets.ReadOnlyModelViewSet):
    """平台订单汇总表。"""
    queryset = PlatformOrderSummary.objects.filter(is_deleted=False)
    serializer_class = PlatformOrderSummarySerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["report_date"]
    ordering_fields = ["report_date"]


class SettlementBatchReportViewSet(viewsets.ReadOnlyModelViewSet):
    """商户结算批次表（实时查询 SettlementBatch）。"""
    queryset = SettlementBatch.objects.filter(is_deleted=False).select_related("merchant", "merchant__agent")
    serializer_class = SettlementBatchReportSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["merchant__merchant_no", "merchant__agent__agent_no", "status", "settle_date"]
    ordering_fields = ["settle_date", "created_at"]


class SettlementDetailReportViewSet(viewsets.ReadOnlyModelViewSet):
    """商户结算明细表（实时查询 SettlementDetail）。"""
    from apps.settlement.serializers import SettlementDetailSerializer
    queryset = SettlementDetail.objects.filter(is_deleted=False).select_related("batch", "batch__merchant", "batch__merchant__agent")
    serializer_class = SettlementDetailSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["batch__batch_no", "batch__merchant__merchant_no", "batch__merchant__agent__agent_no"]
    ordering_fields = ["created_at"]
