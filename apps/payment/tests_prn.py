"""Structured 6-character PRN generation and remark extraction."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.agent.models import Agent
from apps.core.exceptions import BusinessException
from apps.merchant.models import Merchant
from apps.payment.models import PaymentOrder, PrnIssuance
from apps.payment.services.payment import PaymentConfirmService
from apps.payment.services.prn_service import (
    apply_prn,
    bind_prn_to_order,
    extract_prn_from_remark,
    generate_prn,
    is_valid_prn_code,
)
from apps.reconciliation.engine.matcher import ReconciliationMatcher


JAN_1 = date(2026, 1, 1)


class StructuredPrnTests(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(agent_no="AG20260001", agent_name="Alpha Agent")
        self.expire = timezone.now() + timedelta(days=7)

    def _occupy(self, code, agent=None):
        PrnIssuance.objects.create(
            prn_code=code,
            agent=agent or self.agent,
            status=PrnIssuance.Status.ISSUED,
        )

    def test_agent_a_on_jan_1_starts_at_a00101(self):
        with patch("apps.payment.services.prn_service.timezone.localdate", return_value=JAN_1):
            self.assertEqual(generate_prn(agent=self.agent), "A00101")
            self._occupy("A00101")
            self.assertEqual(generate_prn(agent=self.agent), "A00102")

    def test_no_agent_uses_digit_prefix(self):
        with patch("apps.payment.services.prn_service.timezone.localdate", return_value=JAN_1):
            self.assertEqual(generate_prn(), "000101")

    def test_agents_sharing_letter_share_daily_sequence(self):
        other = Agent.objects.create(agent_no="ACME0001", agent_name="Acme Agent")
        with patch("apps.payment.services.prn_service.timezone.localdate", return_value=JAN_1):
            first = generate_prn(agent=self.agent)
            self.assertEqual(first, "A00101")
            self._occupy(first)
            second = generate_prn(agent=other)
            self.assertEqual(second, "A00102")

    def test_daily_sequence_overflow_raises(self):
        self._occupy("A00199")
        with patch("apps.payment.services.prn_service.timezone.localdate", return_value=JAN_1):
            with self.assertRaises(BusinessException) as ctx:
                generate_prn(agent=self.agent)
        self.assertEqual(ctx.exception.code, "INTERNAL_ERROR")

    def test_extract_letter_prn_from_remark(self):
        self.assertEqual(extract_prn_from_remark("PRN:A00101"), "A00101")
        self.assertEqual(extract_prn_from_remark("please pay A00101 today"), "A00101")
        self.assertEqual(extract_prn_from_remark("prn a00101"), "A00101")
        self.assertEqual(extract_prn_from_remark("PRN:123456"), "123456")
        self.assertIsNone(extract_prn_from_remark("PRN:880001"))  # day-of-year 800 invalid
        self.assertEqual(PaymentConfirmService._extract_prn("PRN:A00101"), "A00101")
        self.assertEqual(ReconciliationMatcher._extract_prn("A00101"), "A00101")

    def test_is_valid_prn_code(self):
        self.assertTrue(is_valid_prn_code("A00101"))
        self.assertTrue(is_valid_prn_code("000101"))
        self.assertTrue(is_valid_prn_code("a36699"))
        self.assertFalse(is_valid_prn_code("880001"))
        self.assertFalse(is_valid_prn_code("A00001"))  # day 0
        self.assertFalse(is_valid_prn_code("A36701"))  # day 367
        self.assertFalse(is_valid_prn_code("A00100"))  # seq 0
        self.assertFalse(is_valid_prn_code("PRN_SEARCH_XYZ"))

    def test_bind_rejects_invalid_format_and_regenerates(self):
        merchant = Merchant.objects.create(
            merchant_no="PRN_M002",
            merchant_name="PRN Merchant 2",
            status=Merchant.Status.ACTIVE,
            agent=self.agent,
        )
        order = PaymentOrder.objects.create(
            order_no="PRN_ORD_002",
            merchant_order_no="M_PRN_002",
            unique_identification_no="UIN_PRN_002",
            idempotency_key="IDEM_PRN_002",
            merchant=merchant,
            amount=Decimal("100.00"),
            currency="CNY",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("1.00"),
            settle_amount=Decimal("99.00"),
            status=PaymentOrder.OrderStatus.PENDING_REVIEW,
            pay_method="WIRE_TRANSFER",
            beneficiary_name="Payee",
            expire_at=self.expire,
        )
        with patch("apps.payment.services.prn_service.timezone.localdate", return_value=JAN_1):
            code = bind_prn_to_order(order, "880001")
        self.assertEqual(code, "A00101")

    def test_hmac_apply_uses_agent_prefix(self):
        with patch("apps.payment.services.prn_service.timezone.localdate", return_value=JAN_1):
            issuance = apply_prn(self.agent, amount="10.00", currency="CNY")
        self.assertEqual(issuance.prn_code, "A00101")
        self.assertEqual(len(issuance.prn_code), 6)

    def test_bind_prn_to_order_uses_merchant_agent(self):
        merchant = Merchant.objects.create(
            merchant_no="PRN_M001",
            merchant_name="PRN Merchant",
            status=Merchant.Status.ACTIVE,
            agent=self.agent,
        )
        order = PaymentOrder.objects.create(
            order_no="PRN_ORD_001",
            merchant_order_no="M_PRN_001",
            unique_identification_no="UIN_PRN_001",
            idempotency_key="IDEM_PRN_001",
            merchant=merchant,
            amount=Decimal("100.00"),
            currency="CNY",
            from_currency="USD",
            to_currency="CNY",
            fee_amount=Decimal("1.00"),
            settle_amount=Decimal("99.00"),
            status=PaymentOrder.OrderStatus.PENDING_REVIEW,
            pay_method="WIRE_TRANSFER",
            beneficiary_name="Payee",
            expire_at=self.expire,
        )
        with patch("apps.payment.services.prn_service.timezone.localdate", return_value=JAN_1):
            code = bind_prn_to_order(order, "")
        self.assertEqual(code, "A00101")
