"""Excel 导出工具。"""
from io import BytesIO

from django.http import HttpResponse
from django.utils.http import content_disposition_header


XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def workbook_response(workbook, filename: str) -> HttpResponse:
    """Serialize an openpyxl workbook as an attachment response."""
    buf = BytesIO()
    workbook.save(buf)
    response = HttpResponse(buf.getvalue(), content_type=XLSX_CONTENT_TYPE)
    response["Content-Disposition"] = content_disposition_header(True, filename)
    return response


def excel_response(headers, rows, filename: str) -> HttpResponse:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(list(headers))
    for row in rows:
        ws.append(["" if v is None else v for v in row])
    return workbook_response(wb, filename)
