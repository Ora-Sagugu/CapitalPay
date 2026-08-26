"""对账文件获取测试。"""
import os

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.reconciliation.engine.file_fetcher import BankFileFetcher


@override_settings(BANK_RECON_FETCH_MODE="MOCK")
class BankFileFetcherTest(TestCase):
    def test_mock_fetch_creates_file(self):
        path = BankFileFetcher().fetch_daily_statement("MOCK", timezone.now().date())
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.endswith(".csv"))

    @override_settings(BANK_RECON_FETCH_MODE="SFTP", BANK_SFTP_HOST="")
    def test_sftp_requires_host(self):
        with self.assertRaises(NotImplementedError):
            BankFileFetcher().fetch_daily_statement("MOCK", timezone.now().date())
