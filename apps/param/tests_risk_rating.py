"""Risk rating limit tests."""
from decimal import Decimal

from django.test import TestCase

from apps.param.models import RiskRatingLimit
from apps.param.services import ParamService


class RiskRatingLimitTests(TestCase):
    def setUp(self):
        ParamService.ensure_risk_rating_limits()

    def test_defaults_use_single_times_count(self):
        low = RiskRatingLimit.objects.get(risk_level="LOW")
        self.assertEqual(low.max_single_amount, Decimal("10000.00"))
        self.assertEqual(low.daily_count, 10)
        self.assertEqual(low.daily_limit, Decimal("100000.00"))

    def test_update_recalculates_daily_limit(self):
        row = RiskRatingLimit.objects.get(risk_level="MEDIUM")
        updated = ParamService.update_risk_rating_limit(
            str(row.id),
            {"max_single_amount": Decimal("2000.00"), "daily_count": 4},
        )
        self.assertEqual(updated.daily_limit, Decimal("8000.00"))
        updated.refresh_from_db()
        self.assertEqual(updated.daily_limit, Decimal("8000.00"))

    def test_update_ignores_client_daily_limit(self):
        row = RiskRatingLimit.objects.get(risk_level="HIGH")
        updated = ParamService.update_risk_rating_limit(
            str(row.id),
            {
                "max_single_amount": Decimal("500.00"),
                "daily_count": 2,
                "daily_limit": Decimal("999999.00"),
            },
        )
        self.assertEqual(updated.daily_limit, Decimal("1000.00"))

    def test_list_repairs_stale_daily_limit(self):
        row = RiskRatingLimit.objects.get(risk_level="LOW")
        row.daily_limit = Decimal("1.00")
        row.save(update_fields=["daily_limit"])
        ParamService.list_risk_rating_limits()
        row.refresh_from_db()
        self.assertEqual(row.daily_limit, Decimal("100000.00"))
