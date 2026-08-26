"""对账引擎 — 银行文件获取。"""
import logging
import os
import csv
from datetime import date, datetime

from django.conf import settings

logger = logging.getLogger(__name__)


class BankFileFetcher:
    """银行对账文件获取 — MOCK / SFTP / API。"""

    def fetch_daily_statement(self, bank_code: str, recon_date: date) -> str:
        """获取银行日对账单文件，返回本地路径。"""
        mode = getattr(settings, "BANK_RECON_FETCH_MODE", "MOCK").upper()
        logger.info("recon.fetch mode=%s bank=%s date=%s", mode, bank_code, recon_date)

        if mode == "MOCK":
            return self._fetch_mock(bank_code, recon_date)
        if mode == "SFTP":
            return self._fetch_via_sftp(bank_code, recon_date)
        if mode == "API":
            return self._fetch_via_api(bank_code, recon_date)
        raise ValueError(f"Unknown BANK_RECON_FETCH_MODE: {mode}")

    def _fetch_mock(self, bank_code: str, recon_date: date) -> str:
        local_dir = os.path.join(settings.BASE_DIR, "reconciliation_files")
        os.makedirs(local_dir, exist_ok=True)
        filename = f"{bank_code}_{recon_date.strftime('%Y%m%d')}.csv"
        filepath = os.path.join(local_dir, filename)
        if not os.path.exists(filepath):
            self._generate_mock_statement(filepath, bank_code, recon_date)
        return filepath

    def _fetch_via_sftp(self, bank_code: str, recon_date: date) -> str:
        host = getattr(settings, "BANK_SFTP_HOST", "") or ""
        if not host:
            logger.warning("recon.fetch.sftp blocked: BANK_SFTP_HOST missing")
            raise NotImplementedError("SFTP recon fetch not configured")
        raise NotImplementedError("SFTP recon fetch adapter not implemented")

    def _fetch_via_api(self, bank_code: str, recon_date: date) -> str:
        keys = getattr(settings, "BANK_API_KEYS", {}) or {}
        if not keys.get(bank_code):
            logger.warning("recon.fetch.api blocked: credentials missing for %s", bank_code)
            raise NotImplementedError(f"API recon fetch not configured for {bank_code}")
        raise NotImplementedError("API recon fetch adapter not implemented")

    def _generate_mock_statement(self, filepath: str, bank_code: str, recon_date: date):
        """生成模拟对账文件（仅 MOCK 模式）。"""
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["txn_id", "amount", "txn_time", "type", "remark"])
            for i in range(1, 11):
                txn_time = datetime(
                    recon_date.year, recon_date.month, recon_date.day, 10, i * 5, 0
                )
                writer.writerow([
                    f"MOCK_TXN_{i:06d}",
                    f"{i * 1000:.2f}",
                    txn_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "CREDIT",
                    f"UIN{int(txn_time.timestamp() * 1000)}{i:04d}",
                ])
