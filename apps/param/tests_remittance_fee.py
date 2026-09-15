"""Global remittance fee singleton tests."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.param.models import RemittanceFeeConfig
from apps.param.serializers import RemittanceFeeConfigSerializer
from apps.param.services import compute_remittance_fee
from apps.rbac.models import SystemUser


class RemittanceFeeConfigTests(TestCase):
    def setUp(self):
        self.config = RemittanceFeeConfig.get_config()
        self.config.fixed_fee = Decimal("2.00")
        self.config.percent_rate = Decimal("0.30")
        self.config.max_fee = Decimal("100.00")
        self.config.save()

    def test_get_config_is_singleton(self):
        again = RemittanceFeeConfig.get_config()
        self.assertEqual(self.config.pk, again.pk)
        self.assertEqual(RemittanceFeeConfig.objects.count(), 1)

    def test_one_thousand_is_five(self):
        fee = compute_remittance_fee(Decimal("1000.00"), self.config)
        self.assertEqual(fee, Decimal("5.00"))

    def test_fee_is_capped_at_max(self):
        self.config.percent_rate = Decimal("10.00")
        self.config.max_fee = Decimal("20.00")
        self.config.save()
        fee = compute_remittance_fee(Decimal("1000.00"), self.config)
        self.assertEqual(fee, Decimal("20.00"))

    def test_unconfigured_defaults_to_zero(self):
        RemittanceFeeConfig.objects.all().delete()
        config = RemittanceFeeConfig.get_config()
        self.assertEqual(config.fixed_fee, Decimal("0.00"))
        self.assertEqual(compute_remittance_fee(Decimal("1000.00"), config), Decimal("0.00"))

    def test_update_rejects_max_below_fixed(self):
        ser = RemittanceFeeConfigSerializer(
            self.config,
            data={"fixed_fee": "10.00", "max_fee": "5.00"},
            partial=True,
        )
        self.assertFalse(ser.is_valid())
        self.assertIn("max_fee", ser.errors)

    def test_update_rejects_negative_percent(self):
        ser = RemittanceFeeConfigSerializer(
            self.config,
            data={"percent_rate": "-0.10"},
            partial=True,
        )
        self.assertFalse(ser.is_valid())


class RemittanceFeeConfigApiTests(TestCase):
    def setUp(self):
        RemittanceFeeConfig.get_config()
        self.client = APIClient()
        from apps.rbac.testing import attach_super_admin
        self.user = SystemUser.objects.create(
            username="fee-admin",
            password_hash="test",
            real_name="Fee Admin",
        )
        attach_super_admin(self.user)
        self.client.force_authenticate(self.user)

    def test_get_and_put(self):
        listed = self.client.get("/api/v1/admin/remittance-fee-config/")
        self.assertEqual(listed.status_code, 200, listed.content)
        self.assertIn("fixed_fee", listed.data)
        saved = self.client.put(
            "/api/v1/admin/remittance-fee-config/",
            {"fixed_fee": "2.00", "percent_rate": "0.30", "max_fee": "100.00"},
            format="json",
        )
        self.assertEqual(saved.status_code, 200, saved.content)
        self.assertEqual(saved.data["fixed_fee"], "2.00")
        self.assertEqual(saved.data["percent_rate"], "0.30")
        self.assertEqual(saved.data["max_fee"], "100.00")
        self.assertEqual(saved.data["updated_by"], "fee-admin")

    def test_put_rejects_max_below_fixed(self):
        resp = self.client.put(
            "/api/v1/admin/remittance-fee-config/",
            {"fixed_fee": "10.00", "percent_rate": "0.30", "max_fee": "1.00"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
