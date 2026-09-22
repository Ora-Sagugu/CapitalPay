"""Seed demo data for an Africa-focused B2B remittance corridor.

Usage:
    python manage.py seed_data
    python manage.py seed_data --reset   # wipe business data (keeps OFAC/UN lists)
"""
import hashlib
import random
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.utils import encrypt_field, generate_idempotency_key
from apps.merchant.models import (
    Merchant, MerchantKYC, MerchantFee, MerchantSettlementAccount, MerchantPaymentProduct,
    MerchantSplitConfig, MerchantStatusEvent,
)
from apps.merchant.services import MerchantLifecycleService, ensure_merchant_multi_currency_accounts
from apps.param.models import CoopBank, FeeModel, BankFeeConfig, RemittanceFeeConfig
from apps.payment.models import (
    PaymentOrder, RefundOrder, PrnIssuance, RefundFeeConfig, PRNConfig,
    RemittanceQuote, MerchantDailyRemittanceUsage,
)
from apps.account.models import (
    NostroAccount, UserAccount, FundTransfer, UserPaymentDetail,
    VirtualAccount, VaLedgerEntry, DepositRequest, MoneyMovement,
    AgentDisbursement, DisbursementApproval, AgentDisbursementSchedule,
)
from apps.reconciliation.models import (
    ReconciliationBatch, ReconciliationDiff, NostroBalanceCheck, ReconAlert, ReconAlertConfig,
)
from apps.settlement.models import SettlementBatch, SettlementDetail, FeeShare, DifferenceWriteOff
from apps.payment.services.prn_service import generate_prn
from apps.routing.models import BankChannel, BankTransaction, RoutingRule, RoutingLog


DEMO_RNG_SEED = 20260901
DEMO_PORTAL_PASSWORD = "123456"


def _gmail_from_name(full_name: str) -> str:
    """Grace Nyambura -> gracenyambura@gmail.com (storage / login normalised)."""
    local = "".join((full_name or "").split())
    return f"{local.lower()}@gmail.com"


def _gmail_display(full_name: str) -> str:
    """Grace Nyambura -> GraceNyambura@gmail.com (docs / console)."""
    local = "".join((full_name or "").split())
    return f"{local}@gmail.com"


HORIZON_COUNTERPARTIES = [
    ("Siemens AG", "COMMERZBANK AG", "COBADEFF", "EUR", "Invoice HT-{ref} industrial motors"),
    ("Schneider Electric", "BNP PARIBAS", "BNPAFRPP", "EUR", "Invoice HT-{ref} switchgear"),
    ("ABB Ltd", "UBS SWITZERLAND AG", "UBSWCHZH", "EUR", "Contract HT-EU-{ref} transformers"),
    ("Maersk Line", "CITIBANK NA", "CITIUS33", "USD", "Ocean freight Mombasa HT-{ref}"),
    ("Caterpillar Inc", "JPMORGAN CHASE", "CHASUS33", "USD", "Heavy equipment deposit HT-{ref}"),
    ("DHL Global Forwarding", "DEUTSCHE BANK AG", "DEUTDEFF", "EUR", "Air freight Nairobi HT-{ref}"),
    ("Safaricom PLC", "Equity Bank Kenya", "EQBLKENA", "USD", "Local vendor settlement HT-{ref}"),
    ("Kenya Ports Authority", "Equity Bank Kenya", "EQBLKENA", "USD", "Port handling charges HT-{ref}"),
    ("Atlas Copco", "SEB", "ESSESESS", "EUR", "Compressor package HT-{ref}"),
    ("Honeywell International", "BANK OF AMERICA", "BOFAUS3N", "USD", "Process controls HT-{ref}"),
]

LAGOS_COUNTERPARTIES = [
    ("Olam International", "STANDARD CHARTERED", "SCBLSGSG", "USD", "Cocoa season proceeds LA-{ref}"),
    ("Yara International", "DNB BANK ASA", "DNBANOKK", "USD", "Fertiliser shipment LA-{ref}"),
    ("Cargill Inc", "BANK OF AMERICA", "BOFAUS3N", "USD", "Cashew offtake LA-{ref}"),
    ("Louis Dreyfus Company", "BNP PARIBAS", "BNPAFRPP", "USD", "Sesame contract LA-{ref}"),
    ("Bunge Limited", "CITIBANK NA", "CITIUS33", "USD", "Grain invoice LA-{ref}"),
    ("Wilmar International", "DBS BANK LTD", "DBSSSGSG", "USD", "Palm oil cargo LA-{ref}"),
    ("BASF SE", "DEUTSCHE BANK AG", "DEUTDEFF", "EUR", "Agro-chemicals LA-{ref}"),
    ("Syngenta AG", "UBS SWITZERLAND AG", "UBSWCHZH", "EUR", "Crop protection LA-{ref}"),
]


def _days_ago(n):
    return timezone.now() - timedelta(days=n)


def _hours_ago(n):
    return timezone.now() - timedelta(hours=n)


def _at(days_ago, hour, minute, second=0):
    """Aware datetime on a local calendar day, typically Nairobi business hours."""
    day = timezone.localdate() - timedelta(days=days_ago)
    naive = datetime.combine(day, time(hour, minute, second))
    return timezone.make_aware(naive, timezone.get_current_timezone())


def _stamp(obj, dt, **extra):
    """Backdate auto_now(_add) fields after insert."""
    fields = {"created_at": dt, **extra}
    if hasattr(obj, "updated_at"):
        fields["updated_at"] = extra.get("updated_at", dt)
    type(obj).objects.filter(pk=obj.pk).update(**fields)
    for key, value in fields.items():
        setattr(obj, key, value)
    return obj


def _invoice_amount(low=8200, high=178000):
    dollars = random.randint(low, high)
    cents = random.choice([18, 25, 40, 42, 50, 65, 75, 80, 90, 0, 0])
    return Decimal(f"{dollars}.{cents:02d}")


class Command(BaseCommand):
    help = "Load English Africa-corridor demo data for CapitalPay"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Wipe existing data before seeding")

    def handle(self, *args, **options):
        random.seed(DEMO_RNG_SEED)
        if options["reset"]:
            self._reset_data()

        self.stdout.write(self.style.MIGRATE_HEADING("Seeding Africa corridor demo data (last 7 days)..."))

        agents = self._create_agents()
        merchants = self._create_merchants(agents)
        customers = self._create_merchant_customers(merchants)
        self._create_param_fees()
        nostro_accounts = self._create_nostro_accounts()
        self._create_bank_channels()
        orders = self._create_payment_orders(merchants)
        end_users = self._create_user_portal_data(merchants, agents, orders)
        demo_orders = self._create_demo_workflow_orders(merchants, agents, end_users, customers)
        orders.extend(demo_orders)
        refunds = self._create_refunds(orders)
        self._create_reconciliation(nostro_accounts, orders)
        batches = self._create_settlement(merchants, orders)
        movements = self._create_money_movements(orders, refunds, batches)
        deposits = self._create_deposits(merchants, nostro_accounts)
        va_entries = self._create_va_ledger(merchants, orders)
        notifications = self._create_bank_notifications(orders, nostro_accounts)
        self._create_rbac_data()
        self._create_onboarding(end_users)
        fx_count = self._create_exchange_rates()
        scan_count = self._create_sanction_scans(merchants, orders)
        report_stats = self._create_daily_reports()
        grace_stats = self._enrich_grace_nyambura(agents, merchants, end_users, customers)

        window_from = (timezone.localdate() - timedelta(days=6)).isoformat()
        window_to = timezone.localdate().isoformat()
        self.stdout.write(self.style.SUCCESS("\nDemo data loaded."))
        self.stdout.write(f"  Window: {window_from} to {window_to}")
        self.stdout.write(
            f"  Merchants: {len(merchants)} independent books "
            "(Horizon, Lagos Agro, Cape Coast, Accra Digital suspended)"
        )
        self.stdout.write(f"  Agent customers: {len(customers)} (no portal login)")
        self.stdout.write("  Agents: 3 (Grace holds an East-Africa CURRENT book)")
        self.stdout.write("  Nostro accounts: 3")
        self.stdout.write("  Bank channels: 10 (fee waterfall: ICBC cheapest but low USD balance)")
        self.stdout.write(f"  Payment orders: {len(orders)} (USD, mixed statuses + demo workflow)")
        self.stdout.write(f"  Refunds: {len(refunds)}")
        self.stdout.write(f"  Settlement batches: {len(batches)}")
        self.stdout.write(f"  Money movements: {movements}")
        self.stdout.write(f"  Deposits: {deposits}")
        self.stdout.write(f"  Bank notifications: {notifications}")
        self.stdout.write(f"  VA ledger entries: {va_entries}")
        self.stdout.write(f"  Sanction scans: {scan_count} CLEAR (OFAC/UN lists kept)")
        self.stdout.write(f"  Daily reports: {report_stats}")
        self.stdout.write("  RBAC: 25 functions + 4 roles + 4 ops users")
        self.stdout.write(
            f"  Grace enrichment: +{grace_stats['customers']} customers, "
            f"+{grace_stats['fee_shares']} fee shares, "
            f"CURRENT top-ups on {grace_stats['va_boosted']} books"
        )
        self.stdout.write("  Portals: gmail logins, password 123456")
        self.stdout.write(f"  FX pairs: {fx_count} rows across 7 days")
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Demo logins"))
        self.stdout.write("  Ops console       http://localhost:1025")
        self.stdout.write("    admin / 123456       Super Admin")
        self.stdout.write("    ops / 123456         Merchant Ops")
        self.stdout.write("    compliance / 123456  Compliance / Risk")
        self.stdout.write("    finance / 123456     Finance")
        self.stdout.write("    support / 123456     Customer Support")
        self.stdout.write("    analyst / 123456     Analyst / Read-only")
        self.stdout.write("  Agent portal      http://localhost:1026/login")
        self.stdout.write(f"    {_gmail_display('Grace Nyambura')} / 123456   EastAfrica Collection (rich demo book)")
        self.stdout.write(f"    {_gmail_display('Adewale Balogun')} / 123456  Sahel Corridor")
        self.stdout.write(f"    {_gmail_display('Ama Serwaa')} / 123456       Gulf Coast Collections")
        self.stdout.write("  Merchant portal   http://localhost:1027/login")
        self.stdout.write(f"    {_gmail_display('Amara Wanjiku')} / 123456   Horizon Trade (independent)")
        self.stdout.write(f"    {_gmail_display('Chinedu Okonkwo')} / 123456 Lagos Agro (independent)")
        self.stdout.write(f"    {_gmail_display('Abena Owusu')} / 123456     Cape Coast Export (independent)")
        self.stdout.write("    (SMS mock code: 000000)")
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Demo workflow tips"))
        self.stdout.write("  Agent Orders: PAYDEMOAGENT01 is an agent-booked remittance awaiting CapitalPay")
        self.stdout.write("  Ops Orders: PENDING_REVIEW = CapitalPay application queue; Approve then Confirm transfer")
        self.stdout.write("  Confirm transfer: ICBC leftover USD can be used with a second bank when the payout is larger")
        self.stdout.write("  Grace Earnings: period filters show multi-week / month / quarter Agent Fee history")
        self.stdout.write("  Re-seed: python manage.py seed_data --reset")

    def _reset_data(self):
        self.stdout.write(self.style.WARNING("Wiping business data (keeping OFAC/UN sanction lists)..."))
        from apps.core.data_wipe import wipe_business_data

        # Keep RiskRatingLimit (migration defaults) so re-seed still has limit presets.
        wipe_business_data(keep_risk_rating_limits=True, clear_framework_ephemera=False)
        self.stdout.write("  Cleared (SanctionList preserved)")

    def _create_agents(self):
        self.stdout.write("  Creating agents...")
        from apps.agent.models import Agent, AgentKYC

        a1 = Agent.objects.create(
            agent_no="AG20260001",
            agent_name="EastAfrica Collection Agency Ltd",
            short_name="EastAfrica Collection",
            status="ACTIVE",
            contact_name="Grace Nyambura",
            contact_phone="254722100101",
            contact_email=_gmail_from_name("Grace Nyambura"),
            commission_rate=Decimal("0.500000"),
            max_merchant_count=50,
            legal_person="Grace Nyambura",
            id_type="PASSPORT",
            legal_person_id="A00218473",
            business_license_no="PVT-8YUK2L9",
            registered_capital="USD 1,200,000",
            registered_address="ABC Place, Waiyaki Way, Westlands, Nairobi, Kenya",
            business_scope="Payment collection, merchant onboarding and FX corridor services for East Africa.",
            established_date=_days_ago(365 * 7).date(),
            settlement_bank_name="Equity Bank Kenya",
            settlement_account_no="0180291234567",
            swift_code="EQBLKENA",
            settlement_account_holder="EastAfrica Collection Agency Ltd",
            api_key="ak_eaca_nairobi_001",
            api_secret="sk_eaca_7f3c9a12b8d04e56a1c2d3e4f5a6b7c8",
        )
        AgentKYC.objects.create(
            agent=a1,
            tier=AgentKYC.KycTier.TIER_2,
            legal_person="Grace Nyambura",
            id_type=AgentKYC.IdType.PASSPORT,
            id_number=encrypt_field("A00218473"),
            id_number_plain="A00218473",
            business_license=encrypt_field("PVT-8YUK2L9"),
            business_scope="Payment collection, merchant onboarding and FX corridor services for East Africa.",
            registered_capital=Decimal("1200000"),
            established_date=_days_ago(365 * 7).date(),
            registered_address="ABC Place, Waiyaki Way, Westlands, Nairobi, Kenya",
            kyc_status=AgentKYC.KycStatus.APPROVED,
            submitted_at=_days_ago(200),
            reviewed_by="admin",
            reviewed_at=_days_ago(198),
            review_comment="KYC approved. CBK payment service provider licence on file.",
        )

        a2 = Agent.objects.create(
            agent_no="AG20260002",
            agent_name="Sahel Corridor Partners Ltd",
            short_name="Sahel Corridor",
            status="ACTIVE",
            contact_name="Adewale Balogun",
            contact_phone="234809100202",
            contact_email=_gmail_from_name("Adewale Balogun"),
            commission_rate=Decimal("0.800000"),
            max_merchant_count=30,
            legal_person="Adewale Balogun",
            id_type="PASSPORT",
            legal_person_id="A00933184",
            business_license_no="RC-1928473",
            registered_capital="USD 800,000",
            registered_address="Plot 1425, Ahmadu Bello Way, Victoria Island, Lagos, Nigeria",
            business_scope="West Africa collection, disbursement and agri-export settlement.",
            established_date=_days_ago(365 * 5).date(),
            settlement_bank_name="Guaranty Trust Bank",
            settlement_account_no="0001234567",
            swift_code="GTBINGLA",
            settlement_account_holder="Sahel Corridor Partners Ltd",
            api_key="ak_sahel_lagos_002",
            api_secret="sk_sahel_1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d",
        )
        AgentKYC.objects.create(
            agent=a2,
            tier=AgentKYC.KycTier.TIER_2,
            legal_person="Adewale Balogun",
            id_type=AgentKYC.IdType.PASSPORT,
            id_number=encrypt_field("A00933184"),
            id_number_plain="A00933184",
            business_license=encrypt_field("RC-1928473"),
            business_scope="West Africa collection, disbursement and agri-export settlement.",
            registered_capital=Decimal("800000"),
            established_date=_days_ago(365 * 5).date(),
            registered_address="Plot 1425, Ahmadu Bello Way, Victoria Island, Lagos, Nigeria",
            kyc_status=AgentKYC.KycStatus.APPROVED,
            submitted_at=_days_ago(160),
            reviewed_by="admin",
            reviewed_at=_days_ago(155),
            review_comment="CBN licence verified. Approved for NGN/USD corridor.",
        )

        a3 = Agent.objects.create(
            agent_no="AG20260003",
            agent_name="Gulf Coast Collections Ltd",
            short_name="Gulf Coast Collections",
            status="ACTIVE",
            contact_name="Ama Serwaa",
            contact_phone="233244100303",
            contact_email=_gmail_from_name("Ama Serwaa"),
            commission_rate=Decimal("0.600000"),
            max_merchant_count=40,
            legal_person="Ama Serwaa",
            id_type="PASSPORT",
            legal_person_id="GHA-44829103",
            business_license_no="CS-9284716",
            registered_capital="USD 650,000",
            registered_address="One Airport Square, Airport City, Accra, Ghana",
            business_scope="Gulf of Guinea collection, cocoa/export settlement and FX corridor services.",
            established_date=_days_ago(365 * 6).date(),
            settlement_bank_name="Ecobank Ghana",
            settlement_account_no="1441987654321",
            swift_code="ECOCGHAC",
            settlement_account_holder="Gulf Coast Collections Ltd",
            api_key="ak_gulf_accra_003",
            api_secret="sk_gulf_9f8e7d6c5b4a3210fedcba0987654321",
        )
        AgentKYC.objects.create(
            agent=a3,
            tier=AgentKYC.KycTier.TIER_2,
            legal_person="Ama Serwaa",
            id_type=AgentKYC.IdType.PASSPORT,
            id_number=encrypt_field("GHA-44829103"),
            id_number_plain="GHA-44829103",
            business_license=encrypt_field("CS-9284716"),
            business_scope="Gulf of Guinea collection, cocoa/export settlement and FX corridor services.",
            registered_capital=Decimal("650000"),
            established_date=_days_ago(365 * 6).date(),
            registered_address="One Airport Square, Airport City, Accra, Ghana",
            kyc_status=AgentKYC.KycStatus.APPROVED,
            submitted_at=_days_ago(140),
            reviewed_by="admin",
            reviewed_at=_days_ago(135),
            review_comment="Bank of Ghana payment service provider licence verified.",
        )

        self.stdout.write("    Done: 3 agents")
        from apps.agent.services import ensure_agent_accounts

        for agent in (a1, a2, a3):
            ensure_agent_accounts(agent, "USD")
            ensure_agent_accounts(agent, "EUR")
            ensure_agent_accounts(agent, "CNY")
        return [a1, a2, a3]

    def _create_merchants(self, agents):
        self.stdout.write("  Creating merchants...")
        merchants = []

        m1 = Merchant.objects.create(
            merchant_no="M20260001",
            merchant_name="Horizon Trade Limited",
            short_name="Horizon Trade",
            status=Merchant.Status.PENDING,
            contact_name="Amara Wanjiku",
            contact_phone="254712000101",
            contact_email="amara.wanjiku@horizontrade.co.ke",
            api_key="ak_horizon_ke_001",
            api_secret="sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            legal_person_name="Amara Wanjiku",
            license_expiry_date=_days_ago(-365 * 2).date(),
            risk_level="LOW",
        )
        MerchantKYC.objects.create(
            merchant=m1,
            legal_person="Amara Wanjiku",
            id_number=encrypt_field("28475631"),
            business_license=encrypt_field("PVT-6KRA8H2"),
            business_scope=(
                "Import and wholesale of industrial machinery, electrical equipment and "
                "consumer electronics; bonded warehousing in Nairobi and Mombasa."
            ),
            registered_capital=Decimal("2500000"),
            established_date=_days_ago(365 * 8).date(),
            registered_address="The Address, 11th Floor, Muthangari Drive, Westlands, Nairobi, Kenya",
            id_type="PASSPORT",
            id_number_plain="A00391827",
            nationality="Kenya",
            kyc_status="APPROVED",
            reviewed_at=_days_ago(170),
        )
        MerchantFee.objects.create(
            merchant=m1,
            product_type=MerchantFee.ProductType.WIRE_TRANSFER,
            fee_model=MerchantFee.FeeModel.PERCENTAGE,
            fee_rate=Decimal("0.003"),
            min_fee=Decimal("10.00"),
            max_fee=Decimal("500.00"),
            effective_from=_days_ago(180).date(),
        )
        MerchantFee.objects.create(
            merchant=m1,
            product_type=MerchantFee.ProductType.ONLINE_BANK,
            fee_model=MerchantFee.FeeModel.PERCENTAGE,
            fee_rate=Decimal("0.002"),
            min_fee=Decimal("5.00"),
            max_fee=Decimal("300.00"),
            effective_from=_days_ago(180).date(),
        )
        MerchantSettlementAccount.objects.create(
            merchant=m1,
            bank_name="Equity Bank Kenya",
            bank_branch="Westlands Branch, Nairobi",
            account_name="Horizon Trade Limited",
            account_number=encrypt_field("0180198765432"),
            is_default=True,
        )
        MerchantPaymentProduct.objects.create(
            merchant=m1,
            product_type="WIRE_TRANSFER",
            is_enabled=True,
            max_single_amount=Decimal("5000000"),
            daily_limit=Decimal("20000000"),
        )
        ensure_merchant_multi_currency_accounts(m1)
        m1 = MerchantLifecycleService().activate(
            m1,
            reason_code="SEED_KYC_APPROVED",
            comment="演示商户 KYC 与汇款产品已配置",
            actor="seed-data",
            source="SEED_DATA",
        )
        merchants.append(m1)

        m2 = Merchant.objects.create(
            merchant_no="M20260002",
            merchant_name="Lagos Agro Commodities Ltd",
            short_name="Lagos Agro",
            status=Merchant.Status.PENDING,
            contact_name="Chinedu Okonkwo",
            contact_phone="234803000202",
            contact_email="chinedu.okonkwo@lagosagro.ng",
            api_key="ak_lagos_agro_002",
            api_secret="sk_q7w8e9r0t1y2u3i4o5p6a7s8d9f0g1h2",
            legal_person_name="Chinedu Okonkwo",
            license_expiry_date=_days_ago(-400).date(),
            risk_level="MEDIUM",
        )
        MerchantKYC.objects.create(
            merchant=m2,
            legal_person="Chinedu Okonkwo",
            id_number=encrypt_field("A00721458"),
            business_license=encrypt_field("RC-1847291"),
            business_scope=(
                "Export of cocoa beans, cashew and sesame; import of fertiliser, "
                "agro-chemicals and processing equipment."
            ),
            registered_capital=Decimal("5000000"),
            established_date=_days_ago(365 * 12).date(),
            registered_address="14 Adeola Odeku Street, Victoria Island, Lagos, Nigeria",
            id_type="PASSPORT",
            id_number_plain="A00721458",
            nationality="Nigeria",
            kyc_status="APPROVED",
            reviewed_at=_days_ago(90),
        )
        MerchantFee.objects.create(
            merchant=m2,
            product_type=MerchantFee.ProductType.WIRE_TRANSFER,
            fee_model=MerchantFee.FeeModel.PERCENTAGE,
            fee_rate=Decimal("0.0025"),
            min_fee=Decimal("15.00"),
            max_fee=Decimal("800.00"),
            effective_from=_days_ago(90).date(),
        )
        MerchantSettlementAccount.objects.create(
            merchant=m2,
            bank_name="Guaranty Trust Bank",
            bank_branch="Victoria Island Branch, Lagos",
            account_name="Lagos Agro Commodities Ltd",
            account_number=encrypt_field("0009876543"),
            is_default=True,
        )
        MerchantPaymentProduct.objects.create(
            merchant=m2,
            product_type="WIRE_TRANSFER",
            is_enabled=True,
            max_single_amount=Decimal("3000000"),
            daily_limit=Decimal("10000000"),
        )
        ensure_merchant_multi_currency_accounts(m2)
        m2 = MerchantLifecycleService().activate(
            m2,
            reason_code="SEED_KYC_APPROVED",
            comment="演示商户 KYC 与汇款产品已配置",
            actor="seed-data",
            source="SEED_DATA",
        )
        merchants.append(m2)

        m3 = Merchant.objects.create(
            merchant_no="M20260003",
            merchant_name="Accra Digital Systems Ltd",
            short_name="Accra Digital",
            status=Merchant.Status.SUSPENDED,
            contact_name="Kofi Mensah",
            contact_phone="233244000303",
            contact_email="kofi.mensah@accradigital.gh",
            api_key="ak_accra_digital_003",
            api_secret="sk_z3x4c5v6b7n8m9a1q2w3e4r5t6y7u8i9",
            legal_person_name="Kofi Mensah",
            license_expiry_date=_days_ago(20).date(),
            risk_level="HIGH",
        )
        MerchantKYC.objects.create(
            merchant=m3,
            legal_person="Kofi Mensah",
            id_number=encrypt_field("GHA-726184920-1"),
            business_license=encrypt_field("CS123456789"),
            business_scope="Software development, payment gateway integration and IT managed services.",
            registered_capital=Decimal("800000"),
            established_date=_days_ago(365 * 5).date(),
            registered_address="One Airport Square, Airport City, Accra, Ghana",
            id_type="PASSPORT",
            id_number_plain="G1234581",
            nationality="Ghana",
            kyc_status="WARNING",
            remark="Licence expired. Account suspended pending renewal with the Registrar-General.",
            reviewed_at=_days_ago(25),
        )
        MerchantFee.objects.create(
            merchant=m3,
            product_type=MerchantFee.ProductType.AUTHORIZED,
            fee_model=MerchantFee.FeeModel.FIXED,
            fixed_fee=Decimal("15.00"),
            effective_from=_days_ago(30).date(),
        )
        MerchantSettlementAccount.objects.create(
            merchant=m3,
            bank_name="Ecobank Ghana",
            bank_branch="Airport City Branch, Accra",
            account_name="Accra Digital Systems Ltd",
            account_number=encrypt_field("1441000123456"),
            is_default=True,
        )
        MerchantPaymentProduct.objects.create(
            merchant=m3,
            product_type="AUTHORIZED",
            is_enabled=False,
            max_single_amount=Decimal("50000"),
            daily_limit=Decimal("200000"),
        )
        merchants.append(m3)

        m4 = Merchant.objects.create(
            merchant_no="M20260004",
            merchant_name="Cape Coast Export Ltd",
            short_name="Cape Coast Export",
            status=Merchant.Status.PENDING,
            contact_name="Kwame Asante",
            contact_phone="233244123001",
            contact_email=_gmail_from_name("Kwame Asante"),
            api_key="ak_cape_coast_004",
            api_secret="sk_cape_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            legal_person_name="Kwame Asante",
            license_expiry_date=_days_ago(-365).date(),
            risk_level="LOW",
        )
        MerchantKYC.objects.create(
            merchant=m4,
            legal_person="Kwame Asante",
            id_number=encrypt_field("GHA-55102844"),
            business_license=encrypt_field("CS-4418290"),
            business_scope=(
                "Export of cocoa, timber and processed foods; import of packaging "
                "and light industrial equipment for coastal Ghana."
            ),
            registered_capital=Decimal("1800000"),
            established_date=_days_ago(365 * 9).date(),
            registered_address="15 Commercial Street, Cape Coast, Ghana",
            id_type="PASSPORT",
            id_number_plain="GHA-55102844",
            nationality="Ghana",
            kyc_status="APPROVED",
            reviewed_at=_days_ago(110),
        )
        MerchantFee.objects.create(
            merchant=m4,
            product_type=MerchantFee.ProductType.WIRE_TRANSFER,
            fee_model=MerchantFee.FeeModel.PERCENTAGE,
            fee_rate=Decimal("0.0028"),
            min_fee=Decimal("12.00"),
            max_fee=Decimal("600.00"),
            effective_from=_days_ago(110).date(),
        )
        MerchantSettlementAccount.objects.create(
            merchant=m4,
            bank_name="Ecobank Ghana",
            bank_branch="Cape Coast Branch",
            account_name="Cape Coast Export Ltd",
            account_number=encrypt_field("1441556677889"),
            is_default=True,
        )
        MerchantPaymentProduct.objects.create(
            merchant=m4,
            product_type="WIRE_TRANSFER",
            is_enabled=True,
            max_single_amount=Decimal("2500000"),
            daily_limit=Decimal("8000000"),
        )
        ensure_merchant_multi_currency_accounts(m4)
        m4 = MerchantLifecycleService().activate(
            m4,
            reason_code="SEED_KYC_APPROVED",
            comment="演示商户 KYC 与汇款产品已配置",
            actor="seed-data",
            source="SEED_DATA",
        )
        merchants.append(m4)

        for m in merchants:
            MerchantSplitConfig.objects.get_or_create(
                merchant=m,
                defaults={
                    "auto_split": True,
                    "settlement_cycle": 1,
                    "merchant_ratio": Decimal("0.9700"),
                    "platform_ratio": Decimal("0.0200"),
                    "agent_ratio": Decimal("0.0100"),
                },
            )

        self.stdout.write(f"    Done: {len(merchants)} independent merchants")
        return merchants

    def _create_merchant_customers(self, merchants):
        self.stdout.write("  Creating merchant customers (no portal login)...")
        from apps.agent.models import AgentCustomer

        m1, m2, m3 = merchants[0], merchants[1], merchants[min(2, len(merchants) - 1)]
        specs = [
            (m1, "Horizon Trade Limited", "Amara Wanjiku", "254712000101", "amara.wanjiku@horizontrade.co.ke",
             "Kenya", "The Address, Westlands, Nairobi", "Equity Bank Kenya", "Horizon Trade Limited",
             "0180198765432", "EQBLKENA", AgentCustomer.KycStatus.APPROVED),
            (m1, "Savannah Imports Limited", "Mary Achieng", "254711200501", "mary.achieng@savannahimports.co.ke",
             "Kenya", "Westlands Business Park, Nairobi", "Equity Bank Kenya", "Savannah Imports Limited",
             "0180555012345", "EQBLKENA", AgentCustomer.KycStatus.APPROVED),
            (m1, "Kilimanjaro Freight Ltd", "Hassan Juma", "254722300601", "hassan.juma@kilimanjarofreight.co.ke",
             "Kenya", "Mombasa Road Logistics Hub, Nairobi", "KCB Bank Kenya", "Kilimanjaro Freight Ltd",
             "1100678901234", "KCBLKENX", AgentCustomer.KycStatus.APPROVED),
            (m1, "Mombasa Tea Traders", "Lucy Njeri", "254712345010", "lucy.njeri@mombasatea.ke",
             "Kenya", "Moi Avenue, Mombasa", "Equity Bank Kenya", "Mombasa Tea Traders",
             "0180666011111", "EQBLKENA", AgentCustomer.KycStatus.SUBMITTED),
            (m2, "Lagos Agro Commodities Ltd", "Chinedu Okonkwo", "234803000202", "chinedu.okonkwo@lagosagro.ng",
             "Nigeria", "14 Adeola Odeku Street, Victoria Island, Lagos", "Guaranty Trust Bank",
             "Lagos Agro Commodities Ltd", "0009876543", "GTBINGLA", AgentCustomer.KycStatus.APPROVED),
            (m3, "Cape Coast Export Ltd", "Kwame Asante", "233244123001", "kwame.asante@capecoast.gh",
             "Ghana", "15 Commercial Street, Cape Coast", "Ecobank Ghana", "Cape Coast Export Ltd",
             "1441556677889", "ECOCGHAC", AgentCustomer.KycStatus.APPROVED),
        ]
        created = []
        for merchant, legal, contact, phone, email, nationality, address, bank, account_name, account_no, swift, status in specs:
            row = AgentCustomer.objects.create(
                merchant=merchant,
                agent=None,
                legal_name=legal,
                contact_name=contact,
                contact_phone=phone,
                contact_email=email,
                id_type="passport",
                id_number=f"A{phone[-6:]}",
                nationality=nationality,
                address=address,
                license_expiry_date=_days_ago(-400).date(),
                kyc_status=status,
                reviewer="seed-data" if status == AgentCustomer.KycStatus.APPROVED else "",
                reviewed_at=_days_ago(30) if status == AgentCustomer.KycStatus.APPROVED else None,
                bank_name=bank,
                account_name=account_name,
                bank_account=account_no,
                swift_code=swift,
            )
            created.append(row)

        self.stdout.write(f"    Done: {len(created)} merchant customers")
        return created

    def _create_param_fees(self):
        self.stdout.write("  Creating correspondent banks and fee models...")
        mock, _ = CoopBank.objects.get_or_create(
            bank_code="MOCK",
            defaults={
                "bank_name": "Mock Correspondent Bank",
                "bank_name_en": "Mock Correspondent Bank",
                "country": "Kenya",
                "city": "Nairobi",
                "status": CoopBank.Status.ACTIVE,
                "support_wire": True,
                "nostro_currency": "USD",
            },
        )
        equity, _ = CoopBank.objects.get_or_create(
            bank_code="EQTY",
            defaults={
                "bank_name": "Equity Bank Kenya",
                "bank_name_en": "Equity Bank Kenya",
                "swift_code": "EQBLKENA",
                "country": "Kenya",
                "city": "Nairobi",
                "status": CoopBank.Status.ACTIVE,
                "nostro_currency": "USD",
            },
        )
        model, _ = FeeModel.objects.get_or_create(
            model_code="STD001",
            defaults={
                "model_name": "Standard USD corridor",
                "fee_type": FeeModel.FeeType.FIXED,
                "base_rate": Decimal("0.003"),
                "min_fee": Decimal("8.00"),
                "max_fee": Decimal("500.00"),
                "description": "Standard inbound USD collection fee for East and West Africa.",
            },
        )
        BankFeeConfig.objects.get_or_create(
            bank=mock, fee_model=model, channel_type="wire",
            defaults={"status": BankFeeConfig.Status.ACTIVE, "override_rate": Decimal("0.003")},
        )
        BankFeeConfig.objects.get_or_create(
            bank=equity, fee_model=model, channel_type="online",
            defaults={"status": BankFeeConfig.Status.ACTIVE, "override_rate": Decimal("0.0025")},
        )
        remittance_fee = RemittanceFeeConfig.get_config()
        remittance_fee.fixed_fee = Decimal("2.00")
        remittance_fee.percent_rate = Decimal("0.30")
        remittance_fee.max_fee = Decimal("100.00")
        remittance_fee.updated_by = "seed"
        remittance_fee.save()

    def _create_nostro_accounts(self):
        self.stdout.write("  Creating nostro accounts...")
        accounts = []

        a1 = NostroAccount.objects.create(
            account_no="NOS20260001",
            bank_code="ICBC",
            bank_name="Industrial and Commercial Bank of China",
            account_number=encrypt_field("0180100123456"),
            account_type=NostroAccount.AccountType.COLLECTION,
            currency="USD",
            balance=Decimal("8500000.00"),
            last_reconciled_balance=Decimal("8482500.00"),
            last_reconciled_at=_hours_ago(12),
        )
        accounts.append(a1)

        a2 = NostroAccount.objects.create(
            account_no="NOS20260002",
            bank_code="JPM",
            bank_name="JPMorgan Chase",
            account_number=encrypt_field("0001122334"),
            account_type=NostroAccount.AccountType.SETTLEMENT,
            currency="USD",
            balance=Decimal("5800000.00"),
            last_reconciled_balance=Decimal("5800000.00"),
            last_reconciled_at=_hours_ago(12),
        )
        accounts.append(a2)

        a3 = NostroAccount.objects.create(
            account_no="NOS20260003",
            bank_code="HSBC",
            bank_name="HSBC Holdings",
            account_number=encrypt_field("070012345678"),
            account_type=NostroAccount.AccountType.RESERVE,
            currency="USD",
            balance=Decimal("5200000.00"),
        )
        accounts.append(a3)

        sweeps = [
            (5, Decimal("165000.40"), "Sweep collection to settlement — T+1 payout cover"),
            (3, Decimal("98000.75"), "Mid-week liquidity sweep ICBC → JPMorgan"),
            (1, Decimal("142500.18"), "Sweep collection to settlement for T+1 merchant payouts"),
        ]
        for days, amount, remark in sweeps:
            executed = _at(days, 16, 20)
            day = executed.date().strftime("%Y%m%d")
            transfer = FundTransfer.objects.create(
                transfer_no=f"FT{day}{days:02d}",
                from_account=a1,
                to_account=a2,
                amount=amount,
                currency="USD",
                status=FundTransfer.TransferStatus.SUCCESS,
                executed_at=executed,
                remark=remark,
            )
            _stamp(transfer, executed)

        self.stdout.write(f"    Done: {len(accounts)} nostro accounts")
        return accounts

    def _create_bank_channels(self):
        self.stdout.write("  Creating bank channels (world's top 10 by assets)...")
        # Ranking by total assets (S&P Global / common industry lists). Balances are USD nostro only.
        banks = [
            {"bank_code": "ICBC", "bank_name": "Industrial and Commercial Bank of China", "country": "China",
             "account_number": "0180100123456",
             "channel_type": "wire", "status": "active", "priority": 100,
             "fee_rate": "0.0008", "min_fee": "5.00", "max_fee": "250.00",
             "currency": "USD", "balance": "4500",
             "supported_countries": ["CN", "HK", "US", "GB", "SG"]},
            {"bank_code": "ABC", "bank_name": "Agricultural Bank of China", "country": "China",
             "account_number": "0550010023456",
             "channel_type": "wire", "status": "active", "priority": 98,
             "fee_rate": "0.0011", "min_fee": "8.00", "max_fee": "280.00",
             "currency": "USD", "balance": "7800000",
             "supported_countries": ["CN", "HK", "US", "GB"]},
            {"bank_code": "CCB", "bank_name": "China Construction Bank", "country": "China",
             "account_number": "6217000012345678",
             "channel_type": "online", "status": "active", "priority": 96,
             "fee_rate": "0.0011", "min_fee": "8.00", "max_fee": "280.00",
             "currency": "USD", "balance": "7200000",
             "supported_countries": ["CN", "HK", "US", "GB", "AU"]},
            {"bank_code": "BOC", "bank_name": "Bank of China", "country": "China",
             "account_number": "4563510000123456",
             "channel_type": "wire", "status": "active", "priority": 94,
             "fee_rate": "0.0012", "min_fee": "10.00", "max_fee": "300.00",
             "currency": "USD", "balance": "6500000",
             "supported_countries": ["CN", "HK", "US", "GB", "SG", "AU"]},
            {"bank_code": "JPM", "bank_name": "JPMorgan Chase", "country": "United States",
             "account_number": "0001122334",
             "channel_type": "wire", "status": "active", "priority": 92,
             "fee_rate": "0.0010", "min_fee": "10.00", "max_fee": "350.00",
             "currency": "USD", "balance": "5800000",
             "supported_countries": ["US", "GB", "DE", "SG", "HK"]},
            {"bank_code": "HSBC", "bank_name": "HSBC Holdings", "country": "United Kingdom",
             "account_number": "070012345678",
             "channel_type": "online", "status": "active", "priority": 90,
             "fee_rate": "0.0012", "min_fee": "12.00", "max_fee": "400.00",
             "currency": "USD", "balance": "5200000",
             "supported_countries": ["GB", "HK", "US", "SG", "CN"]},
            {"bank_code": "BAC", "bank_name": "Bank of America", "country": "United States",
             "account_number": "435601234567",
             "channel_type": "ach", "status": "active", "priority": 88,
             "fee_rate": "0.0013", "min_fee": "10.00", "max_fee": "350.00",
             "currency": "USD", "balance": "4800000",
             "supported_countries": ["US", "GB", "CA", "MX"]},
            {"bank_code": "BNP", "bank_name": "BNP Paribas", "country": "France",
             "account_number": "FR7630004000031234567890143",
             "channel_type": "wire", "status": "active", "priority": 86,
             "fee_rate": "0.0014", "min_fee": "12.00", "max_fee": "400.00",
             "currency": "USD", "balance": "4200000",
             "supported_countries": ["FR", "BE", "IT", "GB", "US"]},
            {"bank_code": "CRAG", "bank_name": "Credit Agricole", "country": "France",
             "account_number": "FR7611808009101234567890144",
             "channel_type": "wire", "status": "active", "priority": 84,
             "fee_rate": "0.0015", "min_fee": "12.00", "max_fee": "420.00",
             "currency": "USD", "balance": "3800000",
             "supported_countries": ["FR", "IT", "GB", "US"]},
            {"bank_code": "PSBC", "bank_name": "Postal Savings Bank of China", "country": "China",
             "account_number": "6217990012345678",
             "channel_type": "realtime", "status": "active", "priority": 82,
             "fee_rate": "0.0016", "min_fee": "8.00", "max_fee": "300.00",
             "currency": "USD", "balance": "3400000",
             "supported_countries": ["CN", "HK", "US"]},
        ]
        for b in banks:
            BankChannel.objects.create(**b)

        names = [
            "Horizon Trade Limited", "Pacific Export Partners",
            "Global Steel & Hardware Ltd", "Atlantic Freight Forwarders",
            "Silk Road Trading Co", "Nordic Logistics AG",
            "James Chen", "Maria Santos", "Amina Diallo", "Thomas Weber",
        ]
        txn_count = 0
        bank_prn_seq = 0
        today = timezone.localdate()
        doy = today.timetuple().tm_yday
        for bank in BankChannel.objects.all():
            for _ in range(random.randint(4, 8)):
                amt = round(random.uniform(2500, 85000), 2)
                fee = round(amt * float(bank.fee_rate), 2)
                fee = min(fee, float(bank.max_fee))
                bal = float(bank.balance)
                d = _at(random.randint(0, 6), random.randint(8, 16), random.randint(0, 59))
                bank_prn_seq = (bank_prn_seq % 99) + 1
                # Demo wire refs use prefix 9 + day-of-year + seq (valid PRN shape).
                demo_prn = f"9{doy:03d}{bank_prn_seq:02d}"
                BankTransaction.objects.create(
                    bank=bank,
                    txn_date=d,
                    prn=demo_prn,
                    beneficiary_name=random.choice(names),
                    amount=amt,
                    currency="USD",
                    fee=fee,
                    balance=round(bal - amt, 2),
                )
                txn_count += 1

        self.stdout.write(f"    Done: {len(banks)} channels, {txn_count} wires")

    def _create_payment_orders(self, merchants):
        self.stdout.write("  Creating payment orders (last 7 days)...")
        m1, m2, _m3, _m4 = merchants[:4]
        orders = []
        today = timezone.localdate()
        refund_slots = {(4, 0), (5, 1)}  # Horizon only, applied below
        closed_slots = {(2, 0)}
        seq_by_day = defaultdict(int)
        merchant_day_index = defaultdict(int)

        specs = []
        for days_ago in range(6, -1, -1):
            day = today - timedelta(days=days_ago)
            is_weekend = day.weekday() >= 5
            if is_weekend:
                n_h, n_l = random.randint(2, 3), random.randint(1, 2)
            else:
                n_h, n_l = random.randint(5, 7), random.randint(3, 5)
            for _ in range(n_h):
                specs.append((days_ago, m1, HORIZON_COUNTERPARTIES, "ICBC"))
            for _ in range(n_l):
                specs.append((days_ago, m2, LAGOS_COUNTERPARTIES, "JPM"))

        for days_ago, merch, counterparties, bank_code in specs:
            day = today - timedelta(days=days_ago)
            seq_by_day[day] += 1
            seq = seq_by_day[day]
            idx = merchant_day_index[(merch.id, days_ago)]
            merchant_day_index[(merch.id, days_ago)] = idx + 1

            hour = 8 + (idx * 2 + seq) % 9
            minute = 10 + (idx * 13 + seq * 7) % 45
            created = _at(days_ago, hour, minute, (seq * 3) % 50)
            stamp = day.strftime("%Y%m%d")
            ref = f"{stamp[-4:]}{seq:02d}"
            ben_name, ben_bank, swift, to_ccy, purpose_tpl = counterparties[seq % len(counterparties)]
            amount = _invoice_amount()
            pay_method = "ONLINE_BANK" if idx % 5 == 4 and merch == m1 else "WIRE_TRANSFER"
            fee = self._calc_fee(merch, amount, pay_method)
            settle = amount - fee

            if days_ago == 0:
                status_cycle = ["PENDING_REVIEW", "PENDING_PAY", "PAY_RECEIVED", "PENDING_PAY", "CLOSED"]
                status = status_cycle[idx % len(status_cycle)]
            elif days_ago == 1:
                status = "PENDING_SETTLE" if idx == 0 else ("PAY_RECEIVED" if idx == 1 else "SETTLED")
            else:
                status = "SETTLED"
            if merch == m1 and (days_ago, idx) in refund_slots and status == "SETTLED":
                status = "REFUNDED"
            if (days_ago, idx) in closed_slots:
                status = "CLOSED"

            paid = status not in ("PENDING_REVIEW", "PENDING_PAY", "CLOSED")
            pay_received_at = created + timedelta(hours=1, minutes=20) if paid else None
            settled_at = None
            if status in ("SETTLED", "REFUNDED") and pay_received_at:
                settled_at = pay_received_at + timedelta(hours=22)
            closed_at = created + timedelta(hours=24) if status == "CLOSED" else None
            bank_txn = f"TXN{stamp}{seq:04d}" if paid else None
            notify = "https://api.horizontrade.co.ke/webhooks/payment" if merch == m1 else "https://api.lagosagro.ng/hooks/pay"

            # Approval issues a PRN (PENDING_REVIEW → PENDING_PAY).
            approved = status != "PENDING_REVIEW"
            prn_code = None
            reviewed_by = ""
            reviewed_at = None
            review_comment = ""
            if approved:
                prn_day = timezone.localtime(created).date() if timezone.is_aware(created) else created.date()
                prn_code = generate_prn(agent=getattr(merch, "agent", None), on_date=prn_day)
                reviewed_by = "approver_nkrumah"
                reviewed_at = created + timedelta(minutes=2)
                review_comment = "Approved"

            history = [
                {"status": "PENDING_REVIEW", "time": created.isoformat()},
            ]
            if approved:
                history.append({
                    "status": "PENDING_PAY",
                    "time": (created + timedelta(minutes=2)).isoformat(),
                    "reviewed_by": reviewed_by,
                    "prn_code": prn_code,
                    "bank_code": bank_code,
                })
            if paid:
                history.append({"status": "PAY_RECEIVED", "time": pay_received_at.isoformat()})
            if status in ("PENDING_SETTLE", "SETTLED", "REFUNDED"):
                history.append({"status": "PENDING_SETTLE", "time": (pay_received_at + timedelta(hours=4)).isoformat()})
            if status in ("SETTLED", "REFUNDED") and settled_at:
                history.append({"status": "SETTLED", "time": settled_at.isoformat()})
            if status == "REFUNDED" and settled_at:
                history.append({"status": "REFUNDED", "time": (settled_at + timedelta(hours=6)).isoformat()})
            if status == "CLOSED" and closed_at:
                history.append({"status": "CLOSED", "time": closed_at.isoformat()})

            order = PaymentOrder.objects.create(
                order_no=f"PAY{stamp}{seq:04d}",
                merchant_order_no=f"{'HT' if merch == m1 else 'LA'}-{stamp}-{seq:03d}",
                unique_identification_no=f"UIN{stamp}{seq:04d}",
                prn_code=prn_code,
                merchant=merch,
                user_id=f"U{1000 + seq + days_ago * 20}",
                currency="USD",
                amount=amount,
                fee_amount=fee,
                settle_amount=settle,
                sender_total_amount=amount + fee if pay_method else amount,
                from_currency="USD",
                to_currency=to_ccy,
                fee_bearing="OUR",
                beneficiary_name=ben_name,
                beneficiary_bank=ben_bank,
                beneficiary_swift=swift,
                beneficiary_account=f"{random.randint(10000000, 99999999)}",
                remittance_purpose=purpose_tpl.format(ref=ref),
                pay_method=pay_method,
                bank_code=bank_code,
                bank_txn_id=bank_txn,
                status=status,
                status_history=history,
                reviewed_by=reviewed_by or None,
                reviewed_at=reviewed_at,
                review_comment=review_comment,
                pay_received_at=pay_received_at,
                settled_at=settled_at,
                closed_at=closed_at,
                expire_at=created + timedelta(hours=24),
                idempotency_key=generate_idempotency_key("seed_"),
                notify_url=notify,
                notify_status="SUCCESS" if paid else "PENDING",
                notify_count=1 if paid else 0,
                last_notify_at=pay_received_at if paid else None,
            )
            _stamp(order, created)
            orders.append(order)

        self.stdout.write(f"    Done: {len(orders)} orders")
        return orders

    def _calc_fee(self, merchant, amount, pay_method=None):
        fees = list(merchant.fees.all())
        if pay_method:
            matched = [f for f in fees if f.product_type == pay_method]
            fees = matched or fees
        for fee in fees:
            if fee.fee_model == "PERCENTAGE":
                calc = amount * fee.fee_rate
                if calc < fee.min_fee:
                    return fee.min_fee
                if fee.max_fee and calc > fee.max_fee:
                    return fee.max_fee
                return calc.quantize(Decimal("0.01"))
            if fee.fee_model == "FIXED":
                return fee.fixed_fee
        return Decimal("0.00")

    def _create_refunds(self, orders):
        self.stdout.write("  Creating refunds...")
        refunds = []
        reasons = [
            "Goods not as specified — quality claim on rejected lot",
            "Short shipment versus bill of lading — commercial refund",
            "Duplicate invoice identified after collection",
        ]

        refunded = [o for o in orders if o.status == "REFUNDED"]
        for i, order in enumerate(refunded):
            created = (order.settled_at or order.pay_received_at or order.created_at) + timedelta(hours=6)
            refund = RefundOrder.objects.create(
                refund_no=f"RF{order.order_no[3:]}",
                payment_order=order,
                refund_amount=order.amount,
                refund_reason=reasons[i % len(reasons)],
                status=RefundOrder.RefundStatus.SUCCESS,
                reviewed_by="admin",
                reviewed_at=created,
                bank_refund_id=f"BANK_RF_{order.bank_txn_id}",
                refunded_at=created + timedelta(hours=8),
            )
            _stamp(refund, created)
            refunds.append(refund)

        pending_source = [o for o in orders if o.status == "PAY_RECEIVED"]
        if pending_source:
            order = pending_source[0]
            created = (order.pay_received_at or order.created_at) + timedelta(hours=3)
            refund = RefundOrder.objects.create(
                refund_no=f"RF{order.order_no[3:]}",
                payment_order=order,
                refund_amount=order.amount,
                refund_reason="Customer cancelled shipment prior to vessel departure",
                status=RefundOrder.RefundStatus.PENDING_REVIEW,
            )
            _stamp(refund, created)
            refunds.append(refund)

        self.stdout.write(f"    Done: {len(refunds)} refunds")
        return refunds

    def _create_reconciliation(self, nostro_accounts, orders):
        self.stdout.write("  Creating reconciliation data...")
        banks = [
            ("ICBC", "Industrial and Commercial Bank of China"),
            ("JPM", "JPMorgan Chase"),
        ]
        batch_count = 0
        for days_ago in range(5, 0, -1):
            recon_date = timezone.localdate() - timedelta(days=days_ago)
            started = _at(days_ago, 22, 15)
            completed = started + timedelta(minutes=42)
            for bank_code, bank_name in banks:
                day_orders = [
                    o for o in orders
                    if o.bank_code == bank_code
                    and o.pay_received_at
                    and timezone.localtime(o.pay_received_at).date() == recon_date
                ]
                platform_count = len(day_orders)
                platform_amount = sum((o.amount for o in day_orders), Decimal("0"))
                is_diff = days_ago == 1 and bank_code == "ICBC"
                extra = Decimal("21500.40") if is_diff else Decimal("0")
                bank_count = platform_count + (1 if is_diff else 0)
                bank_amount = platform_amount + extra
                match_count = max(platform_count - (1 if is_diff else 0), 0)
                match_amount = platform_amount - (day_orders[0].amount if is_diff and day_orders else Decimal("0"))
                if match_amount < 0:
                    match_amount = Decimal("0")

                batch = ReconciliationBatch.objects.create(
                    batch_no=f"RECON{recon_date.strftime('%Y%m%d')}{bank_code}",
                    bank_code=bank_code,
                    bank_name=bank_name,
                    reconciliation_date=recon_date,
                    statement_file=f"/data/recon/{bank_code}_{recon_date.strftime('%Y%m%d')}.csv",
                    total_count_bank=bank_count,
                    total_amount_bank=bank_amount,
                    total_count_platform=platform_count,
                    total_amount_platform=platform_amount,
                    match_count=match_count,
                    match_amount=match_amount if is_diff else platform_amount,
                    diff_count=2 if is_diff else 0,
                    diff_amount=extra if is_diff else Decimal("0"),
                    status=ReconciliationBatch.BatchStatus.DIFF if is_diff else ReconciliationBatch.BatchStatus.MATCHED,
                    started_at=started,
                    completed_at=completed,
                )
                _stamp(batch, started)
                batch_count += 1

                if is_diff:
                    ReconciliationDiff.objects.create(
                        batch=batch,
                        diff_type=ReconciliationDiff.DiffType.BANK_ONLY,
                        bank_txn_id=f"{bank_code}{recon_date.strftime('%Y%m%d')}0099",
                        txn_time=started - timedelta(hours=4),
                        amount_bank=extra,
                        amount_platform=None,
                        resolution=ReconciliationDiff.ResolutionType.PENDING,
                    )
                    if day_orders:
                        sample = day_orders[0]
                        ReconciliationDiff.objects.create(
                            batch=batch,
                            diff_type=ReconciliationDiff.DiffType.AMOUNT_DIFF,
                            order_no=sample.order_no,
                            bank_txn_id=sample.bank_txn_id,
                            txn_time=sample.pay_received_at,
                            amount_bank=sample.amount + Decimal("250.00"),
                            amount_platform=sample.amount,
                            resolution=ReconciliationDiff.ResolutionType.ADJUST_PLATFORM,
                            resolution_note="Bank credited FX uplift of USD 250; platform adjusted to statement.",
                            resolved_by="admin",
                            resolved_at=completed,
                        )

        for acc in nostro_accounts[:2]:
            platform_bal = acc.balance
            bank_bal = platform_bal + random.choice([Decimal("0"), Decimal("-1250"), Decimal("3200")])
            NostroBalanceCheck.objects.create(
                check_date=timezone.localdate() - timedelta(days=1),
                nostro_account=acc,
                platform_balance=platform_bal,
                bank_statement_balance=bank_bal,
                difference=bank_bal - platform_bal,
                is_balanced=(bank_bal == platform_bal),
                remark="Auto-matched" if bank_bal == platform_bal else "Immaterial difference — investigate next cycle",
            )

        self.stdout.write(f"    Done: {batch_count} batches + diffs + balance checks")

    def _create_settlement(self, merchants, orders):
        self.stdout.write("  Creating settlement data...")
        today = timezone.localdate()
        groups = defaultdict(list)
        for order in orders:
            if order.status != "SETTLED" or not order.settled_at:
                continue
            created_date = timezone.localtime(order.created_at).date()
            settle_date = created_date + timedelta(days=1)
            if settle_date > today:
                continue
            groups[(order.merchant_id, settle_date)].append(order)

        batches = []
        merchant_by_id = {m.id: m for m in merchants}
        for (merchant_id, settle_date), settled_orders in sorted(groups.items(), key=lambda x: x[0][1]):
            merchant = merchant_by_id[merchant_id]
            total_amount = sum((o.amount for o in settled_orders), Decimal("0"))
            total_fee = sum((o.fee_amount for o in settled_orders), Decimal("0"))
            net = total_amount - total_fee
            settled_at = timezone.make_aware(
                datetime.combine(settle_date, time(11, 30)),
                timezone.get_current_timezone(),
            )
            acct = merchant.settlement_accounts.first()
            batch = SettlementBatch.objects.create(
                batch_no=f"STL{settle_date.strftime('%Y%m%d')}{merchant.merchant_no[-3:]}",
                settle_date=settle_date,
                merchant=merchant,
                total_count=len(settled_orders),
                total_amount=total_amount,
                fee_total=total_fee,
                settle_net_amount=net,
                status=SettlementBatch.SettleStatus.SETTLED,
                settled_at=settled_at,
                currency="USD",
                bank_txn_id=f"PAYOUT{settle_date.strftime('%Y%m%d')}{merchant.merchant_no[-3:]}",
                settlement_account_info={
                    "bank_name": acct.bank_name if acct else "",
                    "account_name": acct.account_name if acct else "",
                    "currency": "USD",
                },
            )
            _stamp(batch, settled_at)
            batches.append(batch)

            for order in settled_orders:
                detail = SettlementDetail.objects.create(
                    batch=batch,
                    payment_order=order,
                    order_no=order.order_no,
                    amount=order.amount,
                    fee=order.fee_amount,
                    settle_amount=order.settle_amount,
                )
                _stamp(detail, settled_at)
                channel = (order.amount * Decimal("0.003")).quantize(Decimal("0.01"))
                share = FeeShare.objects.create(
                    settlement_detail=detail,
                    payment_order=order,
                    agent=order.agent,
                    order_no=order.order_no,
                    merchant_name=order.party_name,
                    agent_name=order.agent.short_name if order.agent_id else "",
                    bank_channel_name=order.bank_code or "",
                    amount=order.amount,
                    total_fee=order.fee_amount,
                    channel_fee=channel,
                    platform_fee=order.fee_amount,
                    agent_fee=Decimal("0"),
                )
                _stamp(share, settled_at)

        write_off_at = _at(1, 15, 40)
        write_off = DifferenceWriteOff.objects.create(
            write_off_no=f"WOF{write_off_at.strftime('%Y%m%d')}001",
            merchant=merchants[0],
            amount=Decimal("250.00"),
            reason="FX uplift on Equity Bank statement — approved write-off after ops review",
            status=DifferenceWriteOff.WriteOffStatus.APPROVED,
            applied_by="admin",
            approved_by="admin",
            approved_at=write_off_at,
        )
        _stamp(write_off, write_off_at)

        self.stdout.write(f"    Done: {len(batches)} settlement batches + write-off")
        return batches

    def _create_money_movements(self, orders, refunds, batches):
        self.stdout.write("  Creating money movements...")
        seq = 0

        def record(**kwargs):
            nonlocal seq
            seq += 1
            occurred = kwargs.pop("occurred_at")
            mv = MoneyMovement.objects.create(
                movement_no=f"MVSEED{seq:06d}",
                occurred_at=occurred,
                **kwargs,
            )
            MoneyMovement.objects.filter(pk=mv.pk).update(created_at=occurred)
            return mv

        received = ("PAY_RECEIVED", "PENDING_SETTLE", "SETTLED", "REFUNDED")
        for order in orders:
            if order.status not in received or not order.pay_received_at:
                continue
            record(
                movement_type=MoneyMovement.MovementType.COLLECTION,
                status=MoneyMovement.MovementStatus.SUCCESS,
                evidence_level=MoneyMovement.EvidenceLevel.BANK_CONFIRMED,
                amount=order.amount,
                currency=order.from_currency or "USD",
                source_type="PAYMENT",
                source_id=str(order.id),
                occurred_at=order.pay_received_at,
                from_party_type="PAYER",
                from_party_id=order.user_id or "",
                to_party_type="MERCHANT",
                to_party_id=str(order.merchant_id or ""),
                bank_code=order.bank_code or "",
                bank_txn_id=order.bank_txn_id or "",
                payment_order=order,
                remark=f"System-confirmed collection {order.order_no}",
            )

        for batch in batches:
            occurred = batch.settled_at or batch.created_at
            acct = (batch.settlement_account_info or {}).get("account_name", "")
            record(
                movement_type=MoneyMovement.MovementType.SETTLEMENT_PAYOUT,
                status=MoneyMovement.MovementStatus.SUCCESS,
                evidence_level=MoneyMovement.EvidenceLevel.BANK_CONFIRMED,
                amount=batch.settle_net_amount,
                currency=batch.currency or "USD",
                source_type="SETTLEMENT_BATCH",
                source_id=str(batch.id),
                occurred_at=occurred,
                from_party_type="PLATFORM",
                to_party_type="MERCHANT",
                to_party_id=str(batch.merchant_id),
                to_account=acct,
                bank_txn_id=batch.bank_txn_id or "",
                settlement_batch=batch,
                remark=f"Settlement payout {batch.batch_no}",
            )

        for refund in refunds:
            if refund.status != RefundOrder.RefundStatus.SUCCESS:
                continue
            occurred = refund.refunded_at or refund.created_at
            order = refund.payment_order
            record(
                movement_type=MoneyMovement.MovementType.REFUND,
                status=MoneyMovement.MovementStatus.SUCCESS,
                evidence_level=MoneyMovement.EvidenceLevel.BANK_CONFIRMED,
                amount=refund.refund_amount,
                currency=order.from_currency or "USD",
                source_type="REFUND",
                source_id=str(refund.id),
                occurred_at=occurred,
                from_party_type="PLATFORM",
                to_party_type="PAYER",
                to_party_id=order.user_id or "",
                bank_code=order.bank_code or "",
                bank_txn_id=refund.bank_refund_id or "",
                payment_order=order,
                refund_order=refund,
                remark=f"Refund {refund.refund_no}",
            )

        self.stdout.write(f"    Done: {seq} movements")
        return seq

    def _create_deposits(self, merchants, nostro_accounts):
        self.stdout.write("  Creating deposit requests...")
        m1, m2 = merchants[0], merchants[1]
        collection = nostro_accounts[0]
        settlement = nostro_accounts[1]
        specs = [
            (m1, collection, Decimal("85000.40"), "APPROVED", 5, 10, 15, "Inbound Equity collection — Horizon working capital"),
            (m2, settlement, Decimal("125400.75"), "APPROVED", 4, 11, 5, "GTBank inbound — cocoa offtake cover"),
            (m1, collection, Decimal("42850.18"), "APPROVED", 3, 14, 40, "Customer prefunding Horizon USD VA"),
            (m2, settlement, Decimal("22000.00"), "REJECTED", 2, 9, 20, "Name mismatch versus settlement account"),
            (m2, settlement, Decimal("67500.25"), "APPROVED", 1, 13, 10, "Lagos Agro top-up ahead of Yara shipment"),
            (m1, collection, Decimal("18500.50"), "PENDING", 0, 8, 45, "Same-day inbound — awaiting ops review"),
        ]
        created_n = 0
        for merchant, account, amount, status, days, hour, minute, remark in specs:
            created = _at(days, hour, minute)
            stamp = created.strftime("%Y%m%d")
            dep = DepositRequest.objects.create(
                deposit_no=f"DEP{stamp}{created_n + 1:03d}",
                merchant=merchant,
                account=account,
                currency="USD",
                amount=amount,
                status=status,
                remark=remark,
                reviewed_by="finance_botha" if status != "PENDING" else None,
                reviewed_at=created + timedelta(hours=2) if status != "PENDING" else None,
                review_comment="Posted to collection account" if status == "APPROVED" else (
                    "Rejected — beneficiary name mismatch" if status == "REJECTED" else ""
                ),
            )
            _stamp(dep, created)
            created_n += 1
        self.stdout.write(f"    Done: {created_n} deposits")
        return created_n

    def _create_bank_notifications(self, orders, nostro_accounts):
        self.stdout.write("  Creating bank credit notifications...")
        from apps.payment.services.bank_notification import ingest_credit

        paid = {
            PaymentOrder.OrderStatus.PAY_RECEIVED,
            PaymentOrder.OrderStatus.PENDING_SETTLE,
            PaymentOrder.OrderStatus.SETTLED,
            PaymentOrder.OrderStatus.REFUNDED,
            PaymentOrder.OrderStatus.REFUNDING,
        }
        banks = list(nostro_accounts or [])
        created = []
        idx = 0
        for order in orders:
            if not order.prn_code or order.status not in paid:
                continue
            bank = banks[idx % len(banks)] if banks else None
            idx += 1
            txn_time = order.pay_received_at or order.created_at or timezone.now()
            note = ingest_credit(
                amount=order.expected_collection_amount(),
                currency=order.from_currency or order.currency or "USD",
                remark=f"PRN:{order.prn_code}",
                prn_code=order.prn_code,
                txn_id=f"BNKSEED{order.order_no[-12:]}",
                txn_time=txn_time,
                bank_code=bank.bank_code if bank else "ICBC",
                bank_name=bank.bank_name if bank else "Industrial and Commercial Bank of China",
                account_no=bank.account_no if bank else "",
                raw_payload={"source": "SEED", "order_no": order.order_no},
            )
            _stamp(note, txn_time)
            created.append(note)

        pending = next(
            (
                order for order in orders
                if order.status == PaymentOrder.OrderStatus.PENDING_PAY and order.prn_code
            ),
            None,
        )
        if pending:
            bank = banks[0] if banks else None
            mismatch_time = timezone.now() - timedelta(minutes=25)
            note = ingest_credit(
                amount=Decimal(pending.expected_collection_amount()) + Decimal("25.00"),
                currency=pending.from_currency or pending.currency or "USD",
                remark=f"PRN:{pending.prn_code}",
                prn_code=pending.prn_code,
                txn_id="BNKSEEDMISMATCH01",
                txn_time=mismatch_time,
                bank_code=bank.bank_code if bank else "ICBC",
                bank_name=bank.bank_name if bank else "Industrial and Commercial Bank of China",
                account_no=bank.account_no if bank else "",
                raw_payload={"source": "SEED", "kind": "MISMATCH"},
            )
            _stamp(note, mismatch_time)
            created.append(note)

        unmatched_time = timezone.now() - timedelta(hours=2)
        bank = banks[0] if banks else None
        unmatched = ingest_credit(
            amount=Decimal("1500.00"),
            currency="USD",
            remark="WALK-IN CASH / NO PRN",
            txn_id="BNKSEEDUNMATCHED01",
            txn_time=unmatched_time,
            bank_code=bank.bank_code if bank else "ICBC",
            bank_name=bank.bank_name if bank else "Industrial and Commercial Bank of China",
            account_no=bank.account_no if bank else "NOS20260001",
            raw_payload={"source": "SEED", "kind": "UNMATCHED"},
        )
        _stamp(unmatched, unmatched_time)
        created.append(unmatched)

        self.stdout.write(f"    Done: {len(created)} bank credit notifications")
        return len(created)

    def _create_va_ledger(self, merchants, orders):
        self.stdout.write("  Creating VA ledger entries...")
        count = 0
        received = ("PAY_RECEIVED", "PENDING_SETTLE", "SETTLED", "REFUNDED")
        for merchant in merchants[:2]:
            va = VirtualAccount.objects.filter(
                merchant=merchant, currency="USD", status=VirtualAccount.VaStatus.ACTIVE, is_deleted=False,
            ).first()
            if not va:
                va = VirtualAccount.objects.filter(
                    merchant=merchant, status=VirtualAccount.VaStatus.ACTIVE, is_deleted=False,
                ).first()
            if not va:
                continue
            balance = Decimal("0.00")
            merchant_orders = sorted(
                [o for o in orders if o.merchant_id == merchant.id and o.status in received],
                key=lambda o: o.pay_received_at or o.created_at,
            )
            for order in merchant_orders:
                occurred = order.pay_received_at or order.created_at
                balance += order.amount
                entry = VaLedgerEntry.objects.create(
                    virtual_account=va,
                    order=order,
                    entry_type=VaLedgerEntry.EntryType.CREDIT,
                    amount=order.amount,
                    balance_after=balance,
                    source_type="PAYMENT",
                    source_id=str(order.id),
                    remark=f"Collection confirmed {order.order_no}",
                )
                _stamp(entry, occurred)
                count += 1
                if order.status == "SETTLED" and order.settled_at:
                    balance -= order.settle_amount
                    debit = VaLedgerEntry.objects.create(
                        virtual_account=va,
                        order=order,
                        entry_type=VaLedgerEntry.EntryType.DEBIT,
                        amount=order.settle_amount,
                        balance_after=balance,
                        source_type="SETTLEMENT",
                        source_id=str(order.id),
                        remark=f"Settlement payout {order.order_no}",
                    )
                    _stamp(debit, order.settled_at)
                    count += 1
                if order.status == "REFUNDED":
                    refunded_at = order.settled_at or occurred
                    balance -= order.amount
                    debit = VaLedgerEntry.objects.create(
                        virtual_account=va,
                        order=order,
                        entry_type=VaLedgerEntry.EntryType.DEBIT,
                        amount=order.amount,
                        balance_after=balance,
                        source_type="REFUND",
                        source_id=str(order.id),
                        remark=f"Refund {order.order_no}",
                    )
                    _stamp(debit, refunded_at + timedelta(hours=8))
                    count += 1
            va.ledger_balance = balance
            va.available_balance = balance
            va.save(update_fields=["ledger_balance", "available_balance", "updated_at"])
        self.stdout.write(f"    Done: {count} ledger entries")
        return count

    def _create_sanction_scans(self, merchants, orders):
        self.stdout.write("  Creating CLEAR sanction scans...")
        from apps.compliance.models import SanctionScanRecord

        count = 0
        for merchant, days in ((merchants[0], 6), (merchants[1], 5)):
            created = _at(days, 9, 5)
            scan = SanctionScanRecord.objects.create(
                scan_no=f"SCN{created.strftime('%Y%m%d')}M{merchant.merchant_no[-2:]}",
                scan_type="MERCHANT_ONBOARDING",
                target_type="MERCHANT",
                target_id=str(merchant.id),
                target_name=merchant.merchant_name,
                status="CLEAR",
                hit_count=0,
                operator="seed-data",
                scan_result={"matches": [], "lists": ["OFAC", "UN"]},
            )
            _stamp(scan, created)
            count += 1

        for i, order in enumerate(orders, start=1):
            created = order.created_at
            scan = SanctionScanRecord.objects.create(
                scan_no=f"SCN{timezone.localtime(created).strftime('%Y%m%d')}{i:04d}",
                scan_type="TRANSACTION",
                target_type="ORDER",
                target_id=str(order.id),
                target_name=order.beneficiary_name,
                status="CLEAR",
                hit_count=0,
                operator="system",
                scan_result={"matches": [], "lists": ["OFAC", "UN"], "order_no": order.order_no},
            )
            _stamp(scan, created)
            count += 1
        self.stdout.write(f"    Done: {count} CLEAR scans")
        return count

    def _create_daily_reports(self):
        self.stdout.write("  Generating daily report snapshots...")
        from apps.report.tasks import generate_daily_reports

        stats = []
        for days_ago in range(6, -1, -1):
            report_date = timezone.localdate() - timedelta(days=days_ago)
            result = generate_daily_reports(report_date)
            stats.append(result)
        self.stdout.write(f"    Done: {len(stats)} days")
        return stats[-1] if stats else {}

    def _create_rbac_data(self):
        self.stdout.write("  Creating RBAC roles and ops users...")
        from apps.rbac.functions import FEATURE_CODES, SYSTEM_ROLE_CODES
        from apps.rbac.services import AuthService

        AuthService().ensure_ops_rbac()
        self.stdout.write(
            f"    Done: {len(FEATURE_CODES)} functions + {len(SYSTEM_ROLE_CODES)} roles "
            "+ ops users admin/ops/compliance/finance/support/analyst (password 123456)"
        )

    def _create_user_portal_data(self, merchants, agents, orders):
        self.stdout.write("  Creating merchant/agent portal users...")
        from apps.user_portal.models import EndUser, UserOnboarding

        m1, m2, _m3, m4 = merchants[0], merchants[1], merchants[2], merchants[3]
        a1, a2, a3 = agents[0], agents[1], agents[2]

        # Independent merchants (no Agent). Login email = NameSurname@gmail.com, password 123456.
        test_users = [
            ("254712000101", DEMO_PORTAL_PASSWORD, "Amara Wanjiku", "Amara Wanjiku", m1, "Kenya"),
            ("234803000202", DEMO_PORTAL_PASSWORD, "Chinedu Okonkwo", "Chinedu Okonkwo", m2, "Nigeria"),
            ("233244200404", DEMO_PORTAL_PASSWORD, "Abena Owusu", "Abena Owusu", m4, "Ghana"),
        ]

        end_users = []
        for phone, password, nickname, real_name, merchant, nationality in test_users:
            email = _gmail_from_name(real_name)
            pwd_hash = hashlib.sha256(f"user:{password}:b2b_user_salt".encode()).hexdigest()
            user = EndUser.objects.create(
                username="".join(real_name.split()),
                phone=phone,
                email=email,
                password_hash=pwd_hash,
                nickname=nickname,
                real_name=real_name,
                is_verified=True,
                default_merchant=merchant,
                portal_role="merchant",
                onboarding_status="approved",
                onboarding_submitted_at=_days_ago(40),
                onboarding_reviewed_at=_days_ago(38),
                onboarding_reviewer="admin",
            )
            UserOnboarding.objects.create(
                user=user,
                legal_name=real_name,
                id_type=UserOnboarding.IdType.PASSPORT,
                id_number=f"A{phone[-6:]}",
                contact_phone=phone,
                nationality=nationality,
                address="Demo registered address",
                agent_code="",
                license_expiry_date=_days_ago(-400).date(),
                bank_name=(
                    "Equity Bank Kenya" if merchant == m1
                    else "Guaranty Trust Bank" if merchant == m2
                    else "Ecobank Ghana"
                ),
                branch_name="Main Branch",
                account_name=merchant.merchant_name,
                bank_account=f"0180{phone[-6:]}",
                agent_review_status=UserOnboarding.AgentReviewStatus.NONE,
            )
            end_users.append(user)

        agent_logins = [
            ("254722100101", DEMO_PORTAL_PASSWORD, "Grace Nyambura", a1, "Kenya"),
            ("234809100202", DEMO_PORTAL_PASSWORD, "Adewale Balogun", a2, "Nigeria"),
            ("233244100303", DEMO_PORTAL_PASSWORD, "Ama Serwaa", a3, "Ghana"),
        ]
        for phone, password, real_name, agent, nationality in agent_logins:
            email = _gmail_from_name(real_name)
            pwd_hash = hashlib.sha256(f"user:{password}:b2b_user_salt".encode()).hexdigest()
            user = EndUser.objects.create(
                username="".join(real_name.split()),
                phone=phone,
                email=email,
                password_hash=pwd_hash,
                nickname=real_name,
                real_name=real_name,
                is_verified=True,
                default_agent=agent,
                portal_role="agent",
                onboarding_status="approved",
                onboarding_submitted_at=_days_ago(50),
                onboarding_reviewed_at=_days_ago(48),
                onboarding_reviewer="admin",
            )
            UserOnboarding.objects.create(
                user=user,
                legal_name=agent.legal_person or real_name,
                id_type=UserOnboarding.IdType.PASSPORT,
                id_number=agent.legal_person_id or f"A{phone[-6:]}",
                contact_phone=phone,
                nationality=nationality,
                address=agent.registered_address or "Demo agent address",
                license_expiry_date=_days_ago(-500).date(),
                bank_name=agent.settlement_bank_name or "",
                branch_name="Head Office",
                account_name=agent.settlement_account_holder or agent.agent_name,
                bank_account=agent.settlement_account_no or "",
                agent_review_status=UserOnboarding.AgentReviewStatus.NONE,
            )
            end_users.append(user)

        UserAccount.objects.create(
            user_id=str(end_users[0].id),
            merchant=m1,
            bank_code="ICBC",
            bank_name="Industrial and Commercial Bank of China",
            account_holder="Amara Wanjiku",
            account_number=encrypt_field("0180277001234"),
            bind_token=encrypt_field("token_wanjiku_001"),
            status=UserAccount.BindStatus.ACTIVE,
            bind_at=_days_ago(30),
        )
        UserAccount.objects.create(
            user_id=str(end_users[0].id),
            merchant=m1,
            bank_code="HSBC",
            bank_name="HSBC Holdings",
            account_holder="Horizon Trade Limited",
            account_number=encrypt_field("0100001234567"),
            bind_token=encrypt_field("token_wanjiku_002"),
            status=UserAccount.BindStatus.ACTIVE,
            bind_at=_days_ago(20),
        )
        UserAccount.objects.create(
            user_id=str(end_users[1].id),
            merchant=m2,
            bank_code="JPM",
            bank_name="JPMorgan Chase",
            account_holder="Chinedu Okonkwo",
            account_number=encrypt_field("0005566778"),
            bind_token=encrypt_field("token_okonkwo_001"),
            status=UserAccount.BindStatus.ACTIVE,
            bind_at=_days_ago(15),
        )

        payment_detail_count = 0
        for i, order in enumerate(orders):
            if order.status in ("PENDING_REVIEW", "PENDING_PAY", "PENDING_AGENT_REVIEW", "CLOSED"):
                continue
            user = end_users[i % 3]
            UserPaymentDetail.objects.create(
                user_id=str(user.id),
                order=order,
                account=None,
                pay_method=order.pay_method,
                amount=order.amount,
                pay_time=order.pay_received_at or order.created_at,
            )
            payment_detail_count += 1

        self.stdout.write(
            f"    Done: {len(end_users)} users (3 independent merchants + 3 agents) + 3 bound accounts + {payment_detail_count} payment details"
        )
        return end_users

    def _enrich_grace_nyambura(self, agents, merchants, end_users, customers):
        """Expand the first merchant's customer book and Grace agent fee history."""
        self.stdout.write("  Enriching Grace Nyambura demo book...")
        from apps.agent.models import AgentCustomer
        from apps.agent.services import get_agent_ledger_va

        a1 = agents[0]
        m1 = merchants[0]
        grace_customers = [row for row in customers if row.merchant_id == m1.id]
        extras = [
            (m1, "Nakuru Horticulture Ltd", "Peter Otieno", "254712345011", "peter.otieno@nakuruhort.ke",
             "Kenya", "Kenyatta Avenue, Nakuru", "Equity Bank Kenya", "Nakuru Horticulture Ltd",
             "0180777022222", "EQBLKENA", AgentCustomer.KycStatus.APPROVED),
            (m1, "Kisumu Grain Brokers", "Brian Kiprop", "254711200512", "brian.kiprop@kisumugrain.ke",
             "Kenya", "Oginga Odinga Street, Kisumu", "KCB Bank Kenya", "Kisumu Grain Brokers",
             "1100888033333", "KCBLKENX", AgentCustomer.KycStatus.APPROVED),
            (m1, "Eldoret Logistics Co", "Esther Mutua", "254711200513", "esther.mutua@eldoretlog.ke",
             "Kenya", "Uganda Road, Eldoret", "Equity Bank Kenya", "Eldoret Logistics Co",
             "0180999044444", "EQBLKENA", AgentCustomer.KycStatus.APPROVED),
        ]
        new_customers = []
        for merchant, legal, contact, phone, email, nationality, address, bank, account_name, account_no, swift, status in extras:
            row = AgentCustomer.objects.create(
                merchant=merchant,
                agent=None,
                legal_name=legal,
                contact_name=contact,
                contact_phone=phone,
                contact_email=email,
                id_type="passport",
                id_number=f"A{phone[-6:]}",
                nationality=nationality,
                address=address,
                license_expiry_date=_days_ago(-400).date(),
                kyc_status=status,
                reviewer="seed-data",
                reviewed_at=_days_ago(40),
                bank_name=bank,
                account_name=account_name,
                bank_account=account_no,
                swift_code=swift,
            )
            new_customers.append(row)
            grace_customers.append(row)

        va_boosted = 0
        for currency, amount in (
            ("USD", Decimal("563671.50")),
            ("EUR", Decimal("198550.00")),
            ("CNY", Decimal("216000.00")),
        ):
            va = get_agent_ledger_va(a1, NostroAccount.AccountType.CURRENT, currency)
            if not va:
                continue
            va.ledger_balance = amount
            va.available_balance = amount
            va.save(update_fields=["ledger_balance", "available_balance", "updated_at"])
            va_boosted += 1

        fee_specs = [
            (1, 0, Decimal("14200.00"), "EUR", "Siemens AG"),
            (2, 1, Decimal("8600.50"), "USD", "Unilever PLC"),
            (4, 2, Decimal("19500.00"), "EUR", "Maersk Line"),
            (6, 0, Decimal("22340.75"), "USD", "Caterpillar Inc"),
            (9, 1, Decimal("11880.00"), "CNY", "Huawei Technologies"),
            (11, 2, Decimal("15720.25"), "USD", "DHL Global Forwarding"),
            (14, 0, Decimal("9800.00"), "EUR", "ABB Ltd"),
            (18, 1, Decimal("26450.00"), "USD", "Nestle SA"),
            (22, 2, Decimal("13200.40"), "EUR", "Schneider Electric"),
            (28, 0, Decimal("30100.00"), "USD", "Honeywell International"),
            (35, 1, Decimal("7450.00"), "USD", "Procter & Gamble"),
            (42, 2, Decimal("18880.60"), "CNY", "Alibaba.com Singapore"),
            (55, 0, Decimal("21600.00"), "EUR", "Atlas Copco"),
            (68, 1, Decimal("10990.00"), "USD", "BASF SE"),
            (82, 2, Decimal("25400.00"), "EUR", "Volvo Group"),
            (95, 0, Decimal("16750.25"), "USD", "Kenya Ports Authority"),
            (110, 1, Decimal("9200.00"), "EUR", "Philips NV"),
            (125, 2, Decimal("27850.00"), "USD", "Cummins Inc"),
            (150, 0, Decimal("14330.00"), "EUR", "Bosch GmbH"),
            (175, 1, Decimal("20500.50"), "USD", "Amazon EU SARL"),
        ]

        fee_share_count = 0
        for idx, (days_ago, customer_idx, amount, to_ccy, beneficiary) in enumerate(fee_specs, start=1):
            created = _at(days_ago, 10 + (idx % 6), 15 + (idx % 30))
            fee = (amount * Decimal("0.003")).quantize(Decimal("0.01"))
            if fee < Decimal("10.00"):
                fee = Decimal("10.00")
            customer = grace_customers[customer_idx % len(grace_customers)]
            agent_fee = fee
            platform_fee = Decimal("0.00")
            channel_fee = (amount * Decimal("0.003")).quantize(Decimal("0.01"))
            order_no = f"PAYGRACE{days_ago:03d}{idx:02d}"
            order = PaymentOrder.objects.create(
                order_no=order_no,
                merchant_order_no=f"GR-{days_ago:03d}-{idx:02d}",
                unique_identification_no=f"UINGRACE{days_ago:03d}{idx:02d}",
                merchant=None,
                agent=a1,
                agent_customer=customer,
                user_id="",
                currency="USD",
                amount=amount,
                fee_amount=fee,
                settle_amount=amount - fee,
                sender_total_amount=amount + fee,
                fee_currency="USD",
                from_currency="USD",
                to_currency=to_ccy,
                fee_bearing="OUR",
                beneficiary_name=beneficiary,
                beneficiary_bank="DEMO CORRESPONDENT BANK",
                beneficiary_swift="DEMOXXXX",
                beneficiary_account=f"ACC{idx:08d}",
                beneficiary_address="Demo beneficiary address",
                remittance_purpose=f"Grace demo fee-share sample {order_no}",
                pay_method="WIRE_TRANSFER",
                bank_code="JPM",
                status=PaymentOrder.OrderStatus.SETTLED,
                agent_review_status=PaymentOrder.AgentReviewStatus.NONE,
                pay_received_at=created + timedelta(hours=2),
                settled_at=created + timedelta(days=1, hours=3),
                status_history=[
                    {"status": "PENDING_REVIEW", "time": created.isoformat()},
                    {"status": "PAY_RECEIVED", "time": (created + timedelta(hours=2)).isoformat()},
                    {"status": "SETTLED", "time": (created + timedelta(days=1, hours=3)).isoformat()},
                ],
                expire_at=created + timedelta(days=3),
                idempotency_key=generate_idempotency_key(f"seed_grace_{idx}_"),
            )
            _stamp(order, created, updated_at=created + timedelta(days=1, hours=3))
            share = FeeShare.objects.create(
                payment_order=order,
                agent=a1,
                order_no=order.order_no,
                merchant_name=customer.legal_name,
                agent_name=a1.short_name,
                bank_channel_name="JPM",
                amount=amount,
                total_fee=fee,
                channel_fee=channel_fee,
                platform_fee=platform_fee,
                agent_fee=agent_fee,
            )
            _stamp(share, created + timedelta(days=1, hours=4))
            fee_share_count += 1

        collection = NostroAccount.objects.filter(account_type="COLLECTION").first()
        if collection:
            for days_ago, amount, remark in (
                (3, Decimal("45000.00"), "EastAfrica working-capital top-up"),
                (8, Decimal("62000.00"), "Corridor float"),
                (16, Decimal("78000.00"), "CURRENT prefunding"),
            ):
                created = _at(days_ago, 11, 20)
                dep = DepositRequest.objects.create(
                    deposit_no=f"DEPGRACE{days_ago:03d}",
                    agent=a1,
                    account=collection,
                    currency="USD",
                    amount=amount,
                    status="APPROVED",
                    source=DepositRequest.DepositSource.AGENT_SELF,
                    remark=remark,
                    reviewed_by="admin",
                    reviewed_at=created + timedelta(hours=1),
                    review_comment="Posted to collection account",
                )
                _stamp(dep, created, updated_at=created + timedelta(hours=1))

        self.stdout.write(
            f"    Done: +{len(new_customers)} customers, "
            f"+{fee_share_count} fee shares, CURRENT boosts={va_boosted}"
        )
        return {
            "merchants": 0,
            "customers": len(new_customers),
            "fee_shares": fee_share_count,
            "va_boosted": va_boosted,
        }

    def _create_demo_workflow_orders(self, merchants, agents, end_users, customers):
        """Agent-booked remittances go straight to CapitalPay review."""
        self.stdout.write("  Creating demo workflow remittance orders...")
        m1 = merchants[0]
        a1, a2 = agents[0], agents[1]
        merchant_user = end_users[0]
        agent_user_h = next(u for u in end_users if u.default_agent_id == a1.id)
        agent_user_l = next(u for u in end_users if u.default_agent_id == a2.id)
        horizon_c = next(c for c in customers if c.legal_name == "Horizon Trade Limited")
        lagos_c = next(c for c in customers if c.legal_name == "Lagos Agro Commodities Ltd")
        created = _at(0, 9, 15)
        expire = created + timedelta(days=2)
        orders = []

        def _fee(amount):
            return (amount * Decimal("0.003")).quantize(Decimal("0.01"))

        amount = Decimal("12500.00")
        fee = _fee(amount)
        o1 = PaymentOrder.objects.create(
            order_no="PAYDEMOAGENT01",
            merchant_order_no="HT-DEMO-AGENT-01",
            unique_identification_no="UINDEMOAGENT01",
            merchant=None,
            agent=a1,
            agent_customer=horizon_c,
            user_id=str(agent_user_h.id),
            currency="USD",
            amount=amount,
            fee_amount=fee,
            settle_amount=amount - fee,
            sender_total_amount=amount + fee,
            fee_currency="USD",
            from_currency="USD",
            to_currency="EUR",
            fee_bearing="OUR",
            beneficiary_name="Siemens AG",
            beneficiary_bank="COMMERZBANK AG",
            beneficiary_swift="COBADEFF",
            beneficiary_account="DE89370400440532013000",
            beneficiary_address="Werner-von-Siemens-Strasse 1, Munich",
            remittance_purpose="Demo: agent-booked remittance awaiting CapitalPay",
            pay_method="WIRE_TRANSFER",
            status=PaymentOrder.OrderStatus.PENDING_REVIEW,
            agent_review_status=PaymentOrder.AgentReviewStatus.NONE,
            status_history=[{"status": "PENDING_REVIEW", "time": created.isoformat()}],
            expire_at=expire,
            idempotency_key=generate_idempotency_key("seed_demo_agent_"),
        )
        _stamp(o1, created)
        orders.append(o1)

        amount = Decimal("18600.50")
        fee = _fee(amount)
        o2 = PaymentOrder.objects.create(
            order_no="PAYDEMOOPS01",
            merchant_order_no="HT-DEMO-OPS-01",
            unique_identification_no="UINDEMOOPS01",
            merchant=m1,
            user_id=str(merchant_user.id),
            currency="USD",
            amount=amount,
            fee_amount=fee,
            settle_amount=amount - fee,
            sender_total_amount=amount + fee,
            fee_currency="USD",
            from_currency="USD",
            to_currency="EUR",
            fee_bearing="OUR",
            beneficiary_name="Schneider Electric",
            beneficiary_bank="BNP PARIBAS",
            beneficiary_swift="BNPAFRPP",
            beneficiary_account="FR1420041010050500013M02606",
            beneficiary_address="35 rue Joseph Monier, Rueil-Malmaison",
            remittance_purpose="Demo: independent merchant awaiting CapitalPay approve",
            pay_method="WIRE_TRANSFER",
            status=PaymentOrder.OrderStatus.PENDING_REVIEW,
            agent_review_status=PaymentOrder.AgentReviewStatus.NONE,
            status_history=[{"status": "PENDING_REVIEW", "time": (created + timedelta(minutes=5)).isoformat()}],
            expire_at=expire,
            idempotency_key=generate_idempotency_key("seed_demo_ops_"),
        )
        _stamp(o2, created + timedelta(minutes=5))
        orders.append(o2)

        amount = Decimal("9800.00")
        fee = _fee(amount)
        reviewed_at = created + timedelta(minutes=20)
        demo_prn = generate_prn(agent=None, on_date=timezone.localdate())
        o3 = PaymentOrder.objects.create(
            order_no="PAYDEMOPAYOUT01",
            merchant_order_no="HT-DEMO-PAYOUT-01",
            unique_identification_no="UINDEMOPAYOUT01",
            prn_code=demo_prn,
            merchant=m1,
            user_id=str(merchant_user.id),
            currency="USD",
            amount=amount,
            fee_amount=fee,
            settle_amount=amount - fee,
            sender_total_amount=amount + fee,
            fee_currency="USD",
            from_currency="USD",
            to_currency="CNY",
            fee_bearing="OUR",
            beneficiary_name="Huawei Technologies",
            beneficiary_bank="Bank of China",
            beneficiary_swift="BKCHCNBJ",
            beneficiary_account="6217000010001234567",
            beneficiary_address="Bantian, Longgang, Shenzhen",
            remittance_purpose="Demo: confirm transfer with fee waterfall",
            pay_method="WIRE_TRANSFER",
            status=PaymentOrder.OrderStatus.PENDING_PAY,
            agent_review_status=PaymentOrder.AgentReviewStatus.NONE,
            reviewed_by="admin",
            reviewed_at=reviewed_at,
            review_comment="Approved",
            status_history=[
                {"status": "PENDING_REVIEW", "time": (created + timedelta(minutes=10)).isoformat()},
                {
                    "status": "PENDING_PAY",
                    "time": reviewed_at.isoformat(),
                    "reviewed_by": "admin",
                    "prn_code": demo_prn,
                },
            ],
            expire_at=expire,
            idempotency_key=generate_idempotency_key("seed_demo_payout_"),
        )
        _stamp(o3, created + timedelta(minutes=10))
        orders.append(o3)

        amount = Decimal("7200.00")
        fee = _fee(amount)
        o4 = PaymentOrder.objects.create(
            order_no="PAYDEMOAGENT02",
            merchant_order_no="LA-DEMO-AGENT-01",
            unique_identification_no="UINDEMOAGENT02",
            merchant=None,
            agent=a2,
            agent_customer=lagos_c,
            user_id=str(agent_user_l.id),
            currency="USD",
            amount=amount,
            fee_amount=fee,
            settle_amount=amount - fee,
            sender_total_amount=amount + fee,
            fee_currency="USD",
            from_currency="USD",
            to_currency="USD",
            fee_bearing="OUR",
            beneficiary_name="Cargill Inc",
            beneficiary_bank="BANK OF AMERICA",
            beneficiary_swift="BOFAUS3N",
            beneficiary_account="9988776655",
            beneficiary_address="15407 McGinty Road West, Wayzata",
            remittance_purpose="Demo: Lagos agent-booked remittance awaiting CapitalPay",
            pay_method="WIRE_TRANSFER",
            status=PaymentOrder.OrderStatus.PENDING_REVIEW,
            agent_review_status=PaymentOrder.AgentReviewStatus.NONE,
            status_history=[{"status": "PENDING_REVIEW", "time": (created + timedelta(minutes=30)).isoformat()}],
            expire_at=expire,
            idempotency_key=generate_idempotency_key("seed_demo_agent2_"),
        )
        _stamp(o4, created + timedelta(minutes=30))
        orders.append(o4)

        self.stdout.write(
            "    Done: 4 demo workflow orders "
            "(2 agent-booked PENDING_REVIEW, 1 merchant review, 1 payout waterfall)"
        )
        return orders


    def _create_onboarding(self, end_users):
        self.stdout.write("  Creating pending KYC onboarding...")
        from apps.user_portal.models import EndUser, UserOnboarding

        phone = "2348091234507"
        real_name = "Ibrahim Musa"
        pwd_hash = hashlib.sha256(f"user:{DEMO_PORTAL_PASSWORD}:b2b_user_salt".encode()).hexdigest()
        user = EndUser.objects.create(
            username="".join(real_name.split()),
            phone=phone,
            email=_gmail_from_name(real_name),
            password_hash=pwd_hash,
            nickname=real_name,
            real_name=real_name,
            is_verified=False,
            portal_role="merchant",
            onboarding_status="pending",
            onboarding_submitted_at=_days_ago(2),
        )
        UserOnboarding.objects.create(
            user=user,
            legal_name=real_name,
            id_type=UserOnboarding.IdType.PASSPORT,
            id_number="A00492817",
            contact_phone=phone,
            nationality="Nigeria",
            address="14 Adeola Hopewell Street, Victoria Island, Lagos, Nigeria",
            agent_code="",
            license_expiry_date=_days_ago(-400).date(),
            bank_name="Guaranty Trust Bank",
            branch_name="Victoria Island Branch",
            account_name=real_name,
            bank_account="0008899001",
            agent_review_status=UserOnboarding.AgentReviewStatus.NONE,
        )
        end_users.append(user)
        self.stdout.write(
            f"    Done: 1 pending independent merchant profile ({_gmail_display(real_name)})"
        )

    def _create_exchange_rates(self):
        self.stdout.write("  Creating FX rates (last 7 days)...")
        from apps.exchange.models import ExchangeRate
        from apps.exchange.providers import DEFAULT_BASE_RATES

        count = 0
        today = timezone.localdate()
        for days_ago in range(6, -1, -1):
            day = today - timedelta(days=days_ago)
            drift = Decimal("1") + Decimal(str(round((random.random() - 0.5) * 0.008, 6)))
            for (from_ccy, to_ccy), rate in DEFAULT_BASE_RATES.items():
                ExchangeRate.objects.create(
                    date=day,
                    from_currency=from_ccy,
                    to_currency=to_ccy,
                    rate=(rate * drift).quantize(Decimal("0.00000001")),
                    source="Bloomberg",
                )
                count += 1
        self.stdout.write(f"    Done: {count} pairs across 7 days")
        return count
