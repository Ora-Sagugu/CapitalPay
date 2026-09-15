"""报表定时任务。"""
from datetime import timedelta

from django.utils import timezone

from .services import ReportGenerator


def generate_daily_reports(report_date=None):
    report_date = report_date or (timezone.now() - timedelta(days=1)).date()
    return ReportGenerator().generate_all(report_date)
