"""汇率 Provider 测试。"""
from django.test import TestCase, override_settings

from apps.exchange.providers import MockFxProvider, RealFxProvider, get_fx_provider


class FxProviderTest(TestCase):
    def test_mock_fetch_rates(self):
        rates = MockFxProvider().fetch_rates()
        self.assertGreater(len(rates), 0)
        self.assertIn("from_currency", rates[0])
        self.assertIn("rate", rates[0])

    @override_settings(BANK_FX_PROVIDER_MODE="MOCK")
    def test_get_fx_provider_mock(self):
        self.assertIsInstance(get_fx_provider(), MockFxProvider)

    @override_settings(BANK_FX_PROVIDER_MODE="REAL", FX_API_KEY="")
    def test_real_provider_requires_key(self):
        with self.assertRaises(NotImplementedError):
            RealFxProvider().fetch_rates()
