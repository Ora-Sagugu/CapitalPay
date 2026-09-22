"""Seed exhibition demo: Agent Tom Lee + Merchant Amy Fox (empty workspaces).

Creates approved login accounts with zero balances and no orders/customers.
Preserves existing Channels, Sanctions and ops SystemUser accounts.

Usage:
    python manage.py seed_exhibition_tom_amy
"""
from __future__ import annotations

import hashlib
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.account.models import (
    AgentDisbursement,
    AgentDisbursementSchedule,
    DepositRequest,
    DisbursementApproval,
    FundTransfer,
    MoneyMovement,
    NostroAccount,
    UserAccount,
    UserPaymentDetail,
    VaLedgerEntry,
    VirtualAccount,
)
from apps.adjustment.models import AdjustmentApplication, AdjustmentApproval
from apps.agent.models import Agent, AgentCustomer, AgentKYC, AgentMerchant
from apps.agent.services import ensure_agent_accounts, get_agent_ledger_va
from apps.core.utils import encrypt_field, generate_idempotency_key
from apps.merchant.models import (
    Merchant,
    MerchantFee,
    MerchantKYC,
    MerchantPaymentProduct,
    MerchantSettlementAccount,
)
from apps.merchant.services import MerchantLifecycleService, ensure_merchant_multi_currency_accounts
from apps.param.models import BankFeeConfig, CoopBank, FeeModel, RemittanceFeeConfig
from apps.param.services import ParamService
from apps.payment.models import PRNConfig, PaymentOrder, RefundOrder
from apps.payment.services.prn_service import generate_prn
from apps.settlement.engine.calculator import SettlementCalculator
from apps.settlement.models import FeeShare, SettlementBatch, SettlementDetail
from apps.user_portal.models import EndUser, UserOnboarding


PASSWORD = "123456"
RNG_SEED = 20260917

TOM = {
    "name": "Tom Lee",
    "email": "tomlee@gmail.com",
    "email_display": "TomLee@gmail.com",
    "phone": "254700100001",
    "agent_no": "AG20260917",
}
AMY = {
    "name": "Amy Fox",
    "email": "amyfox@gmail.com",
    "email_display": "AmyFox@gmail.com",
    "phone": "254700200002",
    "merchant_no": "M20260917",
}

TOM_CUSTOMERS = [
    ("Nairobi Fresh Produce Ltd", "James Otieno", "254711100001", "james.otieno@nairobifresh.ke",
     "Kenya", "Industrial Area, Nairobi", "Equity Bank Kenya", "018011100001", "EQBLKENA"),
    ("Mombasa Port Traders", "Aisha Hassan", "254711100002", "aisha.hassan@mombasaport.ke",
     "Kenya", "Kilindini Road, Mombasa", "KCB Bank Kenya", "110011100002", "KCBLKENX"),
    ("Rift Valley Coffee Co", "Peter Kamau", "254711100003", "peter.kamau@riftcoffee.ke",
     "Kenya", "Kenya Road, Eldoret", "Equity Bank Kenya", "018011100003", "EQBLKENA"),
    ("Lake Victoria Fisheries", "Grace Achieng", "254711100004", "grace.achieng@lakefish.ke",
     "Kenya", "Oginga Odinga St, Kisumu", "Co-operative Bank", "011011100004", "KCOOKENA"),
    ("Nakuru Dairy Exports", "Brian Kiprop", "254711100005", "brian.kiprop@nakurudairy.ke",
     "Kenya", "Kenyatta Ave, Nakuru", "Equity Bank Kenya", "018011100005", "EQBLKENA"),
    ("Thika Textile Mills", "Esther Wanjiru", "254711100006", "esther.wanjiru@thikatex.ke",
     "Kenya", "Garissa Road, Thika", "Absa Bank Kenya", "203011100006", "BARCKENX"),
    ("Malindi Beach Resorts Ltd", "Omar Said", "254711100007", "omar.said@malindibeach.ke",
     "Kenya", "Lamu Road, Malindi", "Equity Bank Kenya", "018011100007", "EQBLKENA"),
]

TOM_KYC_QUEUE = [
    ("Kisii Tea Growers", "Mary Ngetich", "254711100008", "mary.ngetich@kisiitea.ke",
     "Kenya", "Kisii Town", "Equity Bank Kenya", "018011100008", "EQBLKENA", "submitted"),
    ("Kitale Grain Traders", "Daniel Wekesa", "254711100009", "daniel.wekesa@kitalegrain.ke",
     "Kenya", "Kitale", "KCB Bank Kenya", "110011100009", "KCBLKENX", "rejected"),
]

AMY_COUNTERPARTIES = [
    ("Siemens AG", "COMMERZBANK AG", "COBADEFF", "DE89370400440532013000", "EUR"),
    ("Schneider Electric", "BNP PARIBAS", "BNPAFRPP", "FR1420041010050500013M02606", "EUR"),
    ("ABB Ltd", "UBS SWITZERLAND AG", "UBSWCHZH", "CH9300762011623852957", "EUR"),
    ("Maersk Line", "CITIBANK NA", "CITIUS33", "GB29NWBK60161331926819", "USD"),
    ("Caterpillar Inc", "JPMORGAN CHASE", "CHASUS33", "02100002112345", "USD"),
    ("Huawei Technologies", "Bank of China", "BKCHCNBJ", "778812340001", "CNY"),
    ("Li & Fung Ltd", "HSBC Hong Kong", "HSBCHKHH", "HK123456789012", "HKD"),
    ("Unilever PLC", "Barclays Bank", "BARCGB22", "GB29NWBK60161331926820", "GBP"),
]


def _hash_password(password: str) -> str:
    return hashlib.sha256(f"user:{password}:b2b_user_salt".encode()).hexdigest()


def _at(days_ago, hour, minute=0):
    day = timezone.localdate() - timedelta(days=days_ago)
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


def _stamp(obj, dt):
    type(obj).objects.filter(pk=obj.pk).update(created_at=dt, updated_at=dt)
    obj.created_at = dt
    obj.updated_at = dt
    return obj


def _fee(amount: Decimal) -> Decimal:
    return max((amount * Decimal("0.003")).quantize(Decimal("0.01")), Decimal("10.00"))


class Command(BaseCommand):
    help = "Seed Tom Lee (Agent) + Amy Fox (Merchant) exhibition data for system demos"

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(RNG_SEED)
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding Tom Lee / Amy Fox exhibition data..."))

        self._purge_exhibition()
        self._ensure_fee_config()
        self._ensure_params()
        self._ensure_exchange_rates()
        agent = self._create_tom_lee()
        merchant = self._create_amy_fox(agent)
        self._create_platform_nostros(merchant, agent)
        pending_users = self._create_pending_onboarding()

        self.stdout.write(self.style.SUCCESS("\nExhibition seed complete"))
        self.stdout.write(f"  Agent: {TOM['email_display']} / {PASSWORD}  ({agent.short_name})")
        self.stdout.write(f"  Merchant: {AMY['email_display']} / {PASSWORD}  ({merchant.short_name})")
        self.stdout.write("  Orders / money balances / customers: none (empty workspaces)")
        self.stdout.write(f"  Pending KYC queue users: {pending_users}")
        self.stdout.write("  Ops console: admin / 123456 — Channels + Sanctions preserved")

    def _ensure_fee_config(self):
        PRNConfig.get_config()
        cfg = RemittanceFeeConfig.get_config()
        cfg.fixed_fee = Decimal("2.00")
        cfg.percent_rate = Decimal("0.30")
        cfg.max_fee = Decimal("100.00")
        cfg.updated_by = "seed_exhibition_tom_amy"
        cfg.save()

    def _create_tom_lee(self):
        self.stdout.write("  Creating Agent Tom Lee (empty workspace)...")
        EndUser.objects.filter(email__iexact=TOM["email"]).delete()
        Agent.objects.filter(agent_no=TOM["agent_no"]).delete()

        agent = Agent.objects.create(
            agent_no=TOM["agent_no"],
            agent_name="Tom Lee Collection Agency Ltd",
            short_name="Tom Lee Collection",
            status="ACTIVE",
            contact_name=TOM["name"],
            contact_phone=TOM["phone"],
            contact_email=TOM["email"],
            commission_rate=Decimal("0.500000"),
            max_merchant_count=50,
            legal_person=TOM["name"],
            id_type="PASSPORT",
            legal_person_id="A10020030",
            business_license_no="PVT-TOMLEE01",
            registered_capital="USD 900,000",
            registered_address="Two Rivers Mall, Nairobi, Kenya",
            business_scope="Agent collection and FX settlement for East Africa corridors.",
            established_date=_at(365 * 4, 10).date(),
            settlement_bank_name="Equity Bank Kenya",
            settlement_account_no="0180299001001",
            swift_code="EQBLKENA",
            settlement_account_holder="Tom Lee Collection Agency Ltd",
            api_key="ak_tomlee_001",
            api_secret="sk_tomlee_exhibition_secret_001",
        )
        AgentKYC.objects.create(
            agent=agent,
            tier=AgentKYC.KycTier.TIER_2,
            legal_person=TOM["name"],
            id_type=AgentKYC.IdType.PASSPORT,
            id_number=encrypt_field("A10020030"),
            id_number_plain="A10020030",
            business_license=encrypt_field("PVT-TOMLEE01"),
            business_scope=agent.business_scope,
            registered_capital=Decimal("900000"),
            established_date=agent.established_date,
            registered_address=agent.registered_address,
            kyc_status=AgentKYC.KycStatus.APPROVED,
            submitted_at=_at(60, 9),
            reviewed_by="admin",
            reviewed_at=_at(58, 11),
            review_comment="Exhibition KYC approved.",
        )
        for currency in ("USD", "EUR", "CNY", "HKD"):
            ensure_agent_accounts(agent, currency)
        for acc in agent.nostro_accounts.filter(is_deleted=False):
            if acc.account_type == NostroAccount.AccountType.CURRENT:
                acc.bank_name = "Equity Bank Kenya"
                acc.bank_code = "EQBL"
            else:
                acc.bank_name = "JPMorgan Chase"
                acc.bank_code = "JPM"
            acc.balance = Decimal("0.00")
            acc.save(update_fields=["bank_name", "bank_code", "balance", "updated_at"])
        for currency in ("USD", "EUR", "CNY", "HKD"):
            va = get_agent_ledger_va(agent, NostroAccount.AccountType.CURRENT, currency)
            if va:
                va.ledger_balance = Decimal("0.00")
                va.available_balance = Decimal("0.00")
                va.save(update_fields=["ledger_balance", "available_balance", "updated_at"])

        user = EndUser.objects.create(
            username="TomLee",
            phone=TOM["phone"],
            email=TOM["email"],
            password_hash=_hash_password(PASSWORD),
            nickname=TOM["name"],
            real_name=TOM["name"],
            is_verified=True,
            default_agent=agent,
            portal_role="agent",
            onboarding_status="approved",
            onboarding_submitted_at=_at(55, 10),
            onboarding_reviewed_at=_at(53, 14),
            onboarding_reviewer="admin",
        )
        UserOnboarding.objects.create(
            user=user,
            legal_name=TOM["name"],
            id_type=UserOnboarding.IdType.PASSPORT,
            id_number="A10020030",
            contact_phone=TOM["phone"],
            nationality="Kenya",
            address=agent.registered_address,
            license_expiry_date=_at(-500, 10).date(),
            bank_name=agent.settlement_bank_name,
            branch_name="Westlands Branch",
            account_name=agent.settlement_account_holder,
            bank_account=agent.settlement_account_no,
            swift_code=agent.swift_code,
            agent_review_status=UserOnboarding.AgentReviewStatus.NONE,
        )
        return agent

    def _create_amy_customers(self, merchant):
        customers = []
        for idx, (legal, contact, phone, email, nationality, address, bank, acct, swift) in enumerate(TOM_CUSTOMERS, start=1):
            if idx <= 5:
                kyc_status = AgentCustomer.KycStatus.APPROVED
                reviewer = "admin"
                reviewed_at = _at(40 - idx, 10)
                remark = ""
            else:
                kyc_status = AgentCustomer.KycStatus.SUBMITTED
                reviewer = ""
                reviewed_at = None
                remark = "Awaiting KYC review — exhibition queue"
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
                license_expiry_date=_at(-400, 10).date(),
                kyc_status=kyc_status,
                kyc_remark=remark,
                reviewer=reviewer,
                reviewed_at=reviewed_at,
                bank_name=bank,
                account_name=legal,
                bank_account=acct,
                swift_code=swift,
            )
            customers.append(row)
        for idx, (legal, contact, phone, email, nationality, address, bank, acct, swift, kyc) in enumerate(TOM_KYC_QUEUE, start=8):
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
                license_expiry_date=_at(-200, 10).date(),
                kyc_status=kyc,
                kyc_remark="Name mismatch on licence" if kyc == "rejected" else "Submitted for first-pass KYC",
                reviewer="admin" if kyc == "rejected" else "",
                reviewed_at=_at(2, 15) if kyc == "rejected" else None,
                bank_name=bank,
                account_name=legal,
                bank_account=acct,
                swift_code=swift,
            )
            customers.append(row)
        return customers

    def _create_amy_fox(self, agent):
        self.stdout.write("  Creating Merchant Amy Fox (empty workspace)...")
        EndUser.objects.filter(email__iexact=AMY["email"]).delete()
        Merchant.objects.filter(merchant_no=AMY["merchant_no"]).delete()

        merchant = Merchant.objects.create(
            merchant_no=AMY["merchant_no"],
            merchant_name="Amy Fox Trading Limited",
            short_name="Amy Fox Trading",
            status=Merchant.Status.PENDING,
            contact_name=AMY["name"],
            contact_phone=AMY["phone"],
            contact_email=AMY["email"],
            api_key="ak_amyfox_001",
            api_secret="sk_amyfox_exhibition_secret_001",
            legal_person_name=AMY["name"],
            license_expiry_date=_at(-365 * 2, 10).date(),
            risk_level="LOW",
            agent=agent,
        )
        MerchantKYC.objects.create(
            merchant=merchant,
            legal_person=AMY["name"],
            id_number=encrypt_field("A20030040"),
            business_license=encrypt_field("PVT-AMYFOX01"),
            business_scope="Import/export of consumer electronics and industrial supplies.",
            registered_capital=Decimal("1500000"),
            established_date=_at(365 * 6, 10).date(),
            registered_address="Westlands Road, Nairobi, Kenya",
            id_type="PASSPORT",
            id_number_plain="A20030040",
            nationality="Kenya",
            kyc_status="APPROVED",
            reviewed_at=_at(50, 12),
        )
        MerchantFee.objects.create(
            merchant=merchant,
            product_type=MerchantFee.ProductType.WIRE_TRANSFER,
            fee_model=MerchantFee.FeeModel.PERCENTAGE,
            fee_rate=Decimal("0.003"),
            min_fee=Decimal("10.00"),
            max_fee=Decimal("500.00"),
            effective_from=_at(90, 10).date(),
        )
        MerchantSettlementAccount.objects.create(
            merchant=merchant,
            bank_name="Equity Bank Kenya",
            bank_branch="Westlands Branch, Nairobi",
            account_name="Amy Fox Trading Limited",
            account_number=encrypt_field("0180222002002"),
            is_default=True,
        )
        for product in ("WIRE_TRANSFER", "ONLINE_BANK"):
            MerchantPaymentProduct.objects.create(
                merchant=merchant,
                product_type=product,
                is_enabled=True,
                max_single_amount=Decimal("5000000"),
                daily_limit=Decimal("20000000"),
            )
        ensure_merchant_multi_currency_accounts(merchant)
        merchant = MerchantLifecycleService().activate(
            merchant,
            reason_code="SEED_KYC_APPROVED",
            actor="admin",
            comment="Exhibition merchant activated",
        )
        AgentMerchant.objects.update_or_create(
            agent=agent,
            merchant=merchant,
            defaults={
                "commission_rate": agent.commission_rate,
                "effective_from": timezone.localdate(),
                "effective_to": None,
                "is_deleted": False,
            },
        )
        for va in VirtualAccount.objects.filter(merchant=merchant, is_deleted=False):
            va.ledger_balance = Decimal("0.00")
            va.available_balance = Decimal("0.00")
            va.status = VirtualAccount.VaStatus.ACTIVE
            va.save(update_fields=["ledger_balance", "available_balance", "status", "updated_at"])

        user = EndUser.objects.create(
            username="AmyFox",
            phone=AMY["phone"],
            email=AMY["email"],
            password_hash=_hash_password(PASSWORD),
            nickname=AMY["name"],
            real_name=AMY["name"],
            is_verified=True,
            default_merchant=merchant,
            portal_role="merchant",
            onboarding_status="approved",
            onboarding_submitted_at=_at(48, 10),
            onboarding_reviewed_at=_at(46, 15),
            onboarding_reviewer="admin",
        )
        UserOnboarding.objects.create(
            user=user,
            legal_name=AMY["name"],
            id_type=UserOnboarding.IdType.PASSPORT,
            id_number="A20030040",
            contact_phone=AMY["phone"],
            nationality="Kenya",
            address="Westlands Road, Nairobi, Kenya",
            agent_code=TOM["agent_no"],
            license_expiry_date=_at(-400, 10).date(),
            bank_name="Equity Bank Kenya",
            branch_name="Westlands Branch",
            account_name="Amy Fox Trading Limited",
            bank_account="0180222002002",
            agent_review_status=UserOnboarding.AgentReviewStatus.NONE,
        )
        for bank_code, bank_name, number in (
            ("EQBL", "Equity Bank Kenya", "0180222002002"),
            ("HSBC", "HSBC Holdings", "0100888002002"),
            ("JPM", "JPMorgan Chase", "0001122002002"),
        ):
            UserAccount.objects.create(
                user_id=str(user.id),
                merchant=merchant,
                bank_code=bank_code,
                bank_name=bank_name,
                account_holder="Amy Fox Trading Limited",
                account_number=encrypt_field(number),
                bind_token=encrypt_field(f"token_amy_{bank_code.lower()}"),
                status=UserAccount.BindStatus.ACTIVE,
                bind_at=_at(30, 11),
            )
        return merchant

    def _build_history(self, created, status):
        history = [{"status": PaymentOrder.OrderStatus.PENDING_REVIEW, "time": created.isoformat()}]
        pay_received_at = None
        settled_at = None
        if status in (
            PaymentOrder.OrderStatus.PAY_RECEIVED,
            PaymentOrder.OrderStatus.PENDING_SETTLE,
            PaymentOrder.OrderStatus.SETTLED,
            PaymentOrder.OrderStatus.REFUNDING,
            PaymentOrder.OrderStatus.REFUNDED,
        ):
            pay_at = created + timedelta(hours=2)
            history.append({"status": PaymentOrder.OrderStatus.PAY_RECEIVED, "time": pay_at.isoformat()})
            pay_received_at = pay_at
        if status in (
            PaymentOrder.OrderStatus.PENDING_SETTLE,
            PaymentOrder.OrderStatus.SETTLED,
            PaymentOrder.OrderStatus.REFUNDING,
            PaymentOrder.OrderStatus.REFUNDED,
        ):
            history.append({
                "status": PaymentOrder.OrderStatus.PENDING_SETTLE,
                "time": (created + timedelta(hours=5)).isoformat(),
            })
        if status in (
            PaymentOrder.OrderStatus.SETTLED,
            PaymentOrder.OrderStatus.REFUNDING,
            PaymentOrder.OrderStatus.REFUNDED,
        ):
            settled_at = created + timedelta(days=1, hours=1)
            history.append({"status": PaymentOrder.OrderStatus.SETTLED, "time": settled_at.isoformat()})
        if status == PaymentOrder.OrderStatus.REFUNDING:
            history.append({
                "status": PaymentOrder.OrderStatus.REFUNDING,
                "time": (created + timedelta(days=2)).isoformat(),
            })
        if status == PaymentOrder.OrderStatus.REFUNDED:
            history.append({
                "status": PaymentOrder.OrderStatus.REFUNDING,
                "time": (created + timedelta(days=2)).isoformat(),
            })
            history.append({
                "status": PaymentOrder.OrderStatus.REFUNDED,
                "time": (created + timedelta(days=2, hours=6)).isoformat(),
            })
        if status == PaymentOrder.OrderStatus.CLOSED:
            history.append({
                "status": PaymentOrder.OrderStatus.CLOSED,
                "time": (created + timedelta(hours=4)).isoformat(),
            })
        if status == PaymentOrder.OrderStatus.PENDING_PAY:
            history.append({
                "status": PaymentOrder.OrderStatus.PENDING_PAY,
                "time": (created + timedelta(hours=1)).isoformat(),
            })
        return history, pay_received_at, settled_at

    def _create_amy_orders(self, merchant, customers):
        self.stdout.write("  Creating Amy Fox remittance volume...")
        user = EndUser.objects.get(email=AMY["email"])
        status_cycle = [
            PaymentOrder.OrderStatus.SETTLED,
            PaymentOrder.OrderStatus.SETTLED,
            PaymentOrder.OrderStatus.PENDING_SETTLE,
            PaymentOrder.OrderStatus.PAY_RECEIVED,
            PaymentOrder.OrderStatus.PENDING_REVIEW,
            PaymentOrder.OrderStatus.PENDING_PAY,
            PaymentOrder.OrderStatus.CLOSED,
            PaymentOrder.OrderStatus.REFUNDING,
            PaymentOrder.OrderStatus.REFUNDED,
            PaymentOrder.OrderStatus.SETTLED,
        ]
        methods = ["WIRE_TRANSFER", "WALLET", "CARD"]
        eligible = [c for c in customers if c.kyc_status == AgentCustomer.KycStatus.APPROVED] or customers
        orders = []
        for idx in range(1, 41):
            days = (idx % 14) + (idx // 8)
            status = status_cycle[(idx - 1) % len(status_cycle)]
            customer = eligible[(idx - 1) % len(eligible)]
            bene, bank, swift, acct, to_ccy = AMY_COUNTERPARTIES[(idx - 1) % len(AMY_COUNTERPARTIES)]
            amount = Decimal(str(round(random.uniform(4500, 82000), 2)))
            fee = _fee(amount)
            created = _at(days, 9 + (idx % 8), (idx * 7) % 60)
            history, pay_received_at, settled_at = self._build_history(created, status)
            prn = None
            if status not in (
                PaymentOrder.OrderStatus.PENDING_REVIEW,
                PaymentOrder.OrderStatus.PENDING_PAY,
                PaymentOrder.OrderStatus.CLOSED,
            ):
                prn = generate_prn(agent=None, on_date=timezone.localdate() - timedelta(days=days))
            pay_method = methods[(idx - 1) % len(methods)]
            order = PaymentOrder.objects.create(
                order_no=f"PAYAMYFOX{idx:03d}",
                merchant_order_no=f"AF-EXH-{idx:03d}",
                unique_identification_no=f"UINAMYFOX{idx:03d}",
                prn_code=prn,
                merchant=merchant,
                agent_customer=customer,
                user_id=str(user.id),
                currency="USD",
                amount=amount,
                fee_amount=fee,
                settle_amount=amount - fee,
                sender_total_amount=amount + fee,
                fee_currency="USD",
                from_currency="USD",
                to_currency=to_ccy if to_ccy != "GBP" else "EUR",
                fee_bearing="OUR",
                beneficiary_name=bene,
                beneficiary_bank=bank,
                beneficiary_swift=swift,
                beneficiary_account=acct,
                beneficiary_address=customer.address or "Exhibition beneficiary",
                remittance_purpose=f"Amy Fox remittance for {customer.legal_name}",
                pay_method=pay_method,
                bank_code="EQBL" if pay_method == "WIRE_TRANSFER" else "",
                status=status,
                agent_review_status=PaymentOrder.AgentReviewStatus.NONE,
                pay_received_at=pay_received_at,
                settled_at=settled_at,
                status_history=history,
                expire_at=created + timedelta(days=7),
                idempotency_key=generate_idempotency_key(f"exh_amy_{idx}_"),
            )
            _stamp(order, created)
            share = SettlementCalculator().calculate_fee_share(order)
            _stamp(share, settled_at or created)
            orders.append(order)
        return orders

    def _create_tom_orders(self, agent):
        self.stdout.write("  Creating Tom Lee agent-book remittances...")
        status_cycle = [
            PaymentOrder.OrderStatus.SETTLED,
            PaymentOrder.OrderStatus.SETTLED,
            PaymentOrder.OrderStatus.PENDING_SETTLE,
            PaymentOrder.OrderStatus.PAY_RECEIVED,
            PaymentOrder.OrderStatus.PENDING_REVIEW,
            PaymentOrder.OrderStatus.PENDING_PAY,
            PaymentOrder.OrderStatus.SETTLED,
        ]
        methods = ["WIRE_TRANSFER", "WALLET", "CARD"]
        orders = []
        for idx in range(1, 29):
            days = (idx % 12) + (idx // 6)
            status = status_cycle[(idx - 1) % len(status_cycle)]
            bene, bank, swift, acct, to_ccy = AMY_COUNTERPARTIES[(idx + 2) % len(AMY_COUNTERPARTIES)]
            amount = Decimal(str(round(random.uniform(3200, 55000), 2)))
            fee = _fee(amount)
            created = _at(days, 10 + (idx % 6), (idx * 11) % 60)
            history, pay_received_at, settled_at = self._build_history(created, status)
            prn = None
            if status not in (
                PaymentOrder.OrderStatus.PENDING_REVIEW,
                PaymentOrder.OrderStatus.PENDING_PAY,
                PaymentOrder.OrderStatus.CLOSED,
            ):
                prn = generate_prn(agent=agent, on_date=timezone.localdate() - timedelta(days=days))
            pay_method = methods[(idx - 1) % len(methods)]
            order = PaymentOrder.objects.create(
                order_no=f"PAYTOMLEE{idx:03d}",
                merchant_order_no=f"TL-EXH-{idx:03d}",
                unique_identification_no=f"UINTOMLEE{idx:03d}",
                prn_code=prn,
                merchant=None,
                agent=agent,
                agent_customer=None,
                user_id="",
                currency="USD",
                amount=amount,
                fee_amount=fee,
                settle_amount=amount - fee,
                sender_total_amount=amount + fee,
                fee_currency="USD",
                from_currency="USD",
                to_currency=to_ccy if to_ccy != "GBP" else "EUR",
                fee_bearing="OUR",
                beneficiary_name=bene,
                beneficiary_bank=bank,
                beneficiary_swift=swift,
                beneficiary_account=acct,
                beneficiary_address="Exhibition beneficiary",
                remittance_purpose=f"Tom Lee agent-book remittance #{idx}",
                pay_method=pay_method,
                bank_code="EQBL" if pay_method == "WIRE_TRANSFER" else "",
                status=status,
                agent_review_status=PaymentOrder.AgentReviewStatus.NONE,
                pay_received_at=pay_received_at,
                settled_at=settled_at,
                status_history=history,
                expire_at=created + timedelta(days=7),
                idempotency_key=generate_idempotency_key(f"exh_tom_{idx}_"),
            )
            _stamp(order, created)
            share = SettlementCalculator().calculate_fee_share(order)
            _stamp(share, settled_at or created)
            orders.append(order)
        return orders

    def _create_refunds(self, amy_orders, tom_orders=None):
        self.stdout.write("  Creating refunds for ops visibility...")
        refunds = []
        candidates = [
            o for o in amy_orders
            if o.status in (PaymentOrder.OrderStatus.REFUNDED, PaymentOrder.OrderStatus.REFUNDING)
        ]
        for idx, order in enumerate(candidates, start=1):
            status = (
                RefundOrder.RefundStatus.SUCCESS
                if order.status == PaymentOrder.OrderStatus.REFUNDED
                else RefundOrder.RefundStatus.PENDING_REVIEW
            )
            refund = RefundOrder.objects.create(
                refund_no=f"RFAMY{idx:03d}",
                payment_order=order,
                refund_amount=(order.amount * Decimal("0.35")).quantize(Decimal("0.01")),
                refund_reason="Exhibition partial refund / goods return sample",
                status=status,
                reviewed_by="admin" if status == RefundOrder.RefundStatus.SUCCESS else "",
                reviewed_at=_at(1, 14) if status == RefundOrder.RefundStatus.SUCCESS else None,
            )
            _stamp(refund, order.created_at + timedelta(days=2))
            refunds.append(refund)
        settled = [o for o in amy_orders if o.status == PaymentOrder.OrderStatus.SETTLED][:6]
        for idx, order in enumerate(settled, start=len(refunds) + 1):
            refund = RefundOrder.objects.create(
                refund_no=f"RFAMY{idx:03d}",
                payment_order=order,
                refund_amount=(order.amount * Decimal("0.15")).quantize(Decimal("0.01")),
                refund_reason="Customer request — exhibition pending review",
                status=RefundOrder.RefundStatus.PENDING_REVIEW,
            )
            _stamp(refund, _at(0, 11, idx))
            refunds.append(refund)
        tom_settled = [o for o in (tom_orders or []) if o.status == PaymentOrder.OrderStatus.SETTLED][:3]
        for idx, order in enumerate(tom_settled, start=1):
            refund = RefundOrder.objects.create(
                refund_no=f"RFTOM{idx:03d}",
                payment_order=order,
                refund_amount=(order.amount * Decimal("0.12")).quantize(Decimal("0.01")),
                refund_reason="Agent customer partial refund sample",
                status=RefundOrder.RefundStatus.PENDING_REVIEW,
            )
            _stamp(refund, _at(0, 12, idx))
            refunds.append(refund)
        return refunds

    def _create_settlements(self, merchant, agent, amy_orders, tom_orders):
        self.stdout.write("  Creating settlement batches...")
        batches = []
        amy_settled = [o for o in amy_orders if o.status == PaymentOrder.OrderStatus.SETTLED][:8]
        if amy_settled:
            total = sum((o.amount for o in amy_settled), Decimal("0"))
            fee_total = sum((o.fee_amount for o in amy_settled), Decimal("0"))
            batch = SettlementBatch.objects.create(
                batch_no="SBAMY001",
                settle_date=timezone.localdate() - timedelta(days=1),
                merchant=merchant,
                total_count=len(amy_settled),
                total_amount=total,
                fee_total=fee_total,
                settle_net_amount=total - fee_total,
                currency="USD",
                status=SettlementBatch.SettleStatus.SETTLED,
                settled_at=_at(1, 16),
                settlement_account_info={
                    "bank_name": "Equity Bank Kenya",
                    "account_name": "Amy Fox Trading Limited",
                    "account_number": "****2002",
                },
            )
            _stamp(batch, _at(1, 16))
            for order in amy_settled:
                detail = SettlementDetail.objects.create(
                    batch=batch,
                    payment_order=order,
                    order_no=order.order_no,
                    amount=order.amount,
                    fee=order.fee_amount,
                    settle_amount=order.settle_amount,
                )
                _stamp(detail, _at(1, 16))
            batches.append(batch)

        tom_settled = [o for o in tom_orders if o.status == PaymentOrder.OrderStatus.SETTLED][:6]
        if tom_settled:
            total = sum((o.amount for o in tom_settled), Decimal("0"))
            fee_total = sum((o.fee_amount for o in tom_settled), Decimal("0"))
            batch = SettlementBatch.objects.create(
                batch_no="SBTOM001",
                settle_date=timezone.localdate() - timedelta(days=2),
                agent=agent,
                total_count=len(tom_settled),
                total_amount=total,
                fee_total=fee_total,
                settle_net_amount=total - fee_total,
                currency="USD",
                status=SettlementBatch.SettleStatus.SETTLED,
                settled_at=_at(2, 17),
                settlement_account_info={
                    "bank_name": "Equity Bank Kenya",
                    "account_name": "Tom Lee Collection Agency Ltd",
                    "account_number": "****1001",
                },
            )
            _stamp(batch, _at(2, 17))
            for order in tom_settled:
                detail = SettlementDetail.objects.create(
                    batch=batch,
                    payment_order=order,
                    order_no=order.order_no,
                    amount=order.amount,
                    fee=order.fee_amount,
                    settle_amount=order.settle_amount,
                )
                _stamp(detail, _at(2, 17))
            batches.append(batch)

        amy_pending = [o for o in amy_orders if o.status == PaymentOrder.OrderStatus.PENDING_SETTLE][:6]
        if amy_pending:
            total = sum((o.amount for o in amy_pending), Decimal("0"))
            fee_total = sum((o.fee_amount for o in amy_pending), Decimal("0"))
            batch = SettlementBatch.objects.create(
                batch_no="SBAMY002",
                settle_date=timezone.localdate(),
                merchant=merchant,
                total_count=len(amy_pending),
                total_amount=total,
                fee_total=fee_total,
                settle_net_amount=total - fee_total,
                currency="USD",
                status=SettlementBatch.SettleStatus.PENDING,
                settlement_account_info={
                    "bank_name": "Equity Bank Kenya",
                    "account_name": "Amy Fox Trading Limited",
                    "account_number": "****2002",
                },
            )
            _stamp(batch, _at(0, 9))
            for order in amy_pending:
                detail = SettlementDetail.objects.create(
                    batch=batch,
                    payment_order=order,
                    order_no=order.order_no,
                    amount=order.amount,
                    fee=order.fee_amount,
                    settle_amount=order.settle_amount,
                )
                _stamp(detail, _at(0, 9))
            batches.append(batch)

        tom_pending = [o for o in tom_orders if o.status == PaymentOrder.OrderStatus.PENDING_SETTLE][:4]
        if tom_pending:
            total = sum((o.amount for o in tom_pending), Decimal("0"))
            fee_total = sum((o.fee_amount for o in tom_pending), Decimal("0"))
            batch = SettlementBatch.objects.create(
                batch_no="SBTOM002",
                settle_date=timezone.localdate(),
                agent=agent,
                total_count=len(tom_pending),
                total_amount=total,
                fee_total=fee_total,
                settle_net_amount=total - fee_total,
                currency="USD",
                status=SettlementBatch.SettleStatus.PROCESSING,
                settlement_account_info={
                    "bank_name": "Equity Bank Kenya",
                    "account_name": "Tom Lee Collection Agency Ltd",
                    "account_number": "****1001",
                },
            )
            _stamp(batch, _at(0, 10))
            for order in tom_pending:
                detail = SettlementDetail.objects.create(
                    batch=batch,
                    payment_order=order,
                    order_no=order.order_no,
                    amount=order.amount,
                    fee=order.fee_amount,
                    settle_amount=order.settle_amount,
                )
                _stamp(detail, _at(0, 10))
            batches.append(batch)
        return batches

    def _create_va_ledgers(self, merchant, agent, orders):
        self.stdout.write("  Creating VA ledger activity...")
        merchant_va = VirtualAccount.objects.filter(
            merchant=merchant, currency="USD", is_deleted=False
        ).first()
        agent_va = get_agent_ledger_va(agent, NostroAccount.AccountType.CURRENT, "USD")
        count = 0
        for order in orders:
            if order.status not in (
                PaymentOrder.OrderStatus.PAY_RECEIVED,
                PaymentOrder.OrderStatus.PENDING_SETTLE,
                PaymentOrder.OrderStatus.SETTLED,
                PaymentOrder.OrderStatus.REFUNDING,
                PaymentOrder.OrderStatus.REFUNDED,
            ):
                continue
            va = agent_va if order.agent_id else merchant_va
            if not va:
                continue
            credit = VaLedgerEntry.objects.create(
                virtual_account=va,
                order=order,
                entry_type=VaLedgerEntry.EntryType.CREDIT,
                amount=order.amount,
                balance_after=va.ledger_balance,
                source_type="PAYMENT",
                source_id=order.order_no,
                remark=f"Collection {order.order_no}",
            )
            _stamp(credit, order.pay_received_at or order.created_at)
            count += 1
            if order.status in (
                PaymentOrder.OrderStatus.SETTLED,
                PaymentOrder.OrderStatus.REFUNDING,
                PaymentOrder.OrderStatus.REFUNDED,
            ):
                debit = VaLedgerEntry.objects.create(
                    virtual_account=va,
                    order=order,
                    entry_type=VaLedgerEntry.EntryType.DEBIT,
                    amount=order.settle_amount,
                    balance_after=va.ledger_balance,
                    source_type="SETTLEMENT",
                    source_id=order.order_no,
                    remark=f"Payout {order.order_no}",
                )
                _stamp(debit, order.settled_at or order.created_at)
                count += 1
        self.stdout.write(f"    VA ledger rows: {count}")

    def _create_payment_details(self, merchant, agent, orders):
        amy = EndUser.objects.get(email=AMY["email"])
        tom = EndUser.objects.get(email=TOM["email"])
        for order in orders:
            if order.status in (
                PaymentOrder.OrderStatus.PENDING_REVIEW,
                PaymentOrder.OrderStatus.PENDING_PAY,
                PaymentOrder.OrderStatus.CLOSED,
            ):
                continue
            user = tom if order.agent_id else amy
            UserPaymentDetail.objects.create(
                user_id=str(user.id),
                order=order,
                account=None,
                pay_method=order.pay_method,
                amount=order.amount,
                pay_time=order.pay_received_at or order.created_at,
            )

    def _create_bank_txns(self):
        from apps.routing.models import BankChannel, BankTransaction

        self.stdout.write("  Adding channel wire samples for ops Channels...")
        today = timezone.localdate()
        doy = today.timetuple().tm_yday
        seq = 0
        names = [c[0] for c in AMY_COUNTERPARTIES] + [c[0] for c in TOM_CUSTOMERS]
        for bank in BankChannel.objects.all():
            for _ in range(8):
                seq = (seq % 90) + 1
                amt = Decimal(str(round(random.uniform(2500, 75000), 2)))
                fee = amt * bank.fee_rate
                fee = min(fee, bank.max_fee)
                d = _at(random.randint(0, 6), random.randint(8, 16), random.randint(0, 59))
                BankTransaction.objects.create(
                    bank=bank,
                    txn_date=d,
                    prn=f"9{doy:03d}{seq:02d}",
                    beneficiary_name=random.choice(names),
                    amount=amt,
                    currency="USD",
                    fee=fee,
                    balance=bank.balance - amt,
                )

    def _purge_exhibition(self):
        from django.db.models import Q

        from apps.compliance.models import SanctionHitDetail, SanctionScanRecord
        from apps.merchant.models import MerchantStatusEvent
        from apps.payment.models import BankCreditNotification, PrnIssuance
        from apps.reconciliation.models import NostroBalanceCheck, ReconAlert, ReconciliationBatch, ReconciliationDiff
        from apps.report.models import MerchantDailyReport
        from apps.routing.models import BankTransaction

        self.stdout.write("  Clearing previous Tom/Amy exhibition rows...")
        order_q = (
            Q(order_no__startswith="PAYAMYFOX")
            | Q(order_no__startswith="PAYTOMLEE")
            | Q(merchant__merchant_no=AMY["merchant_no"])
            | Q(agent__agent_no=TOM["agent_no"])
        )
        orders = PaymentOrder.objects.filter(order_q)
        MoneyMovement.objects.filter(payment_order__in=orders).delete()
        VaLedgerEntry.objects.filter(
            Q(order__in=orders)
            | Q(source_id__startswith="PAYAMYFOX")
            | Q(source_id__startswith="PAYTOMLEE")
        ).delete()
        UserPaymentDetail.objects.filter(order__in=orders).delete()
        RefundOrder.objects.filter(
            Q(refund_no__startswith="RFAMY") | Q(refund_no__startswith="RFTOM") | Q(payment_order__in=orders)
        ).delete()
        FeeShare.objects.filter(
            Q(order_no__startswith="PAYAMYFOX") | Q(order_no__startswith="PAYTOMLEE") | Q(payment_order__in=orders)
        ).delete()
        SettlementDetail.objects.filter(
            Q(batch__batch_no__startswith="SBAMY")
            | Q(batch__batch_no__startswith="SBTOM")
            | Q(payment_order__in=orders)
        ).delete()
        SettlementBatch.objects.filter(Q(batch_no__startswith="SBAMY") | Q(batch_no__startswith="SBTOM")).delete()
        BankCreditNotification.objects.filter(Q(txn_id__startswith="BNKEXH") | Q(order__in=orders)).delete()
        DisbursementApproval.objects.filter(disbursement__disbursement_no__startswith="DBEXH").delete()
        AgentDisbursement.objects.filter(disbursement_no__startswith="DBEXH").delete()
        DepositRequest.objects.filter(
            Q(deposit_no__startswith="DEPEXH")
            | Q(merchant__merchant_no=AMY["merchant_no"])
            | Q(agent__agent_no=TOM["agent_no"])
        ).delete()
        FundTransfer.objects.filter(transfer_no__startswith="FTEXH").delete()
        AdjustmentApproval.objects.filter(application__application_no__startswith="ADJEXH").delete()
        AdjustmentApplication.objects.filter(application_no__startswith="ADJEXH").delete()
        ReconAlert.objects.filter(batch__batch_no__startswith="RECONEXH").delete()
        ReconciliationDiff.objects.filter(batch__batch_no__startswith="RECONEXH").delete()
        ReconciliationBatch.objects.filter(batch_no__startswith="RECONEXH").delete()
        NostroBalanceCheck.objects.filter(nostro_account__account_no__startswith="NOSEXH").delete()
        SanctionHitDetail.objects.filter(scan_record__scan_no__startswith="SCNEXH").delete()
        SanctionScanRecord.objects.filter(scan_no__startswith="SCNEXH").delete()
        BankTransaction.objects.all().delete()
        PrnIssuance.objects.filter(prn_code__in=orders.exclude(prn_code="").values_list("prn_code", flat=True)).delete()
        orders.delete()

        emails = [TOM["email"], AMY["email"], "chrispark@gmail.com", "sarahkim@gmail.com"]
        EndUser.objects.filter(email__in=emails).delete()
        UserAccount.objects.filter(merchant__merchant_no=AMY["merchant_no"]).delete()
        AgentDisbursementSchedule.objects.filter(agent__agent_no=TOM["agent_no"]).delete()
        DisbursementApproval.objects.filter(
            Q(disbursement__disbursement_no__startswith="DBEXH")
            | Q(disbursement__agent__agent_no=TOM["agent_no"])
        ).delete()
        AgentDisbursement.objects.filter(
            Q(disbursement_no__startswith="DBEXH") | Q(agent__agent_no=TOM["agent_no"])
        ).delete()
        VaLedgerEntry.objects.filter(
            Q(virtual_account__agent__agent_no=TOM["agent_no"])
            | Q(virtual_account__merchant__merchant_no=AMY["merchant_no"])
        ).delete()
        AgentCustomer.objects.filter(
            Q(agent__agent_no=TOM["agent_no"]) | Q(merchant__merchant_no=AMY["merchant_no"])
        ).delete()
        VirtualAccount.objects.filter(
            Q(agent__agent_no=TOM["agent_no"]) | Q(merchant__merchant_no=AMY["merchant_no"])
        ).delete()
        FundTransfer.objects.filter(
            Q(from_account__account_no__startswith="NOSEXH") | Q(to_account__account_no__startswith="NOSEXH")
        ).delete()
        NostroAccount.objects.filter(
            Q(account_no__startswith="NOSEXH")
            | Q(agent__agent_no=TOM["agent_no"])
            | Q(merchant__merchant_no=AMY["merchant_no"])
        ).delete()
        AgentKYC.objects.filter(agent__agent_no=TOM["agent_no"]).delete()
        MerchantDailyReport.objects.filter(merchant__merchant_no=AMY["merchant_no"]).delete()
        MerchantStatusEvent.objects.filter(merchant__merchant_no=AMY["merchant_no"]).delete()
        MerchantPaymentProduct.objects.filter(merchant__merchant_no=AMY["merchant_no"]).delete()
        MerchantSettlementAccount.objects.filter(merchant__merchant_no=AMY["merchant_no"]).delete()
        MerchantFee.objects.filter(merchant__merchant_no=AMY["merchant_no"]).delete()
        MerchantKYC.objects.filter(merchant__merchant_no=AMY["merchant_no"]).delete()
        Agent.objects.filter(agent_no=TOM["agent_no"]).delete()
        Merchant.objects.filter(merchant_no=AMY["merchant_no"]).delete()

    def _ensure_params(self):
        self.stdout.write("  Ensuring parameter tables...")
        ParamService.ensure_risk_rating_limits()
        banks = [
            ("EQTY", "Equity Bank Kenya", "EQBLKENA", "Kenya", "Nairobi"),
            ("JPM", "JPMorgan Chase", "CHASUS33", "United States", "New York"),
            ("HSBC", "HSBC Holdings", "HSBCHKHH", "Hong Kong", "Hong Kong"),
            ("ICBC", "Industrial and Commercial Bank of China", "ICBKCNBJ", "China", "Beijing"),
        ]
        created_banks = []
        for code, name, swift, country, city in banks:
            bank, _ = CoopBank.objects.get_or_create(
                bank_code=code,
                defaults={
                    "bank_name": name,
                    "bank_name_en": name,
                    "swift_code": swift,
                    "country": country,
                    "city": city,
                    "status": CoopBank.Status.ACTIVE,
                    "support_wire": True,
                    "nostro_currency": "USD",
                },
            )
            created_banks.append(bank)
        model, _ = FeeModel.objects.get_or_create(
            model_code="STD001",
            defaults={
                "model_name": "Standard USD corridor",
                "fee_type": FeeModel.FeeType.FIXED,
                "base_rate": Decimal("0.003"),
                "min_fee": Decimal("8.00"),
                "max_fee": Decimal("500.00"),
                "description": "Standard inbound USD collection fee.",
            },
        )
        for bank, channel in ((created_banks[0], "online"), (created_banks[1], "wire")):
            BankFeeConfig.objects.get_or_create(
                bank=bank,
                fee_model=model,
                channel_type=channel,
                defaults={"status": BankFeeConfig.Status.ACTIVE, "override_rate": Decimal("0.003")},
            )

    def _ensure_exchange_rates(self):
        from apps.exchange.models import ExchangeRate
        from apps.exchange.providers import DEFAULT_BASE_RATES

        self.stdout.write("  Ensuring FX rates...")
        today = timezone.localdate()
        count = 0
        for days_ago in range(6, -1, -1):
            day = today - timedelta(days=days_ago)
            drift = Decimal("1") + Decimal(str(round((random.random() - 0.5) * 0.008, 6)))
            for (from_ccy, to_ccy), rate in DEFAULT_BASE_RATES.items():
                ExchangeRate.objects.get_or_create(
                    date=day,
                    from_currency=from_ccy,
                    to_currency=to_ccy,
                    defaults={
                        "rate": (rate * drift).quantize(Decimal("0.00000001")),
                        "source": "Bloomberg",
                    },
                )
                count += 1
        self.stdout.write(f"    FX pairs: {count}")

    def _create_platform_nostros(self, merchant, agent):
        self.stdout.write("  Creating platform nostro accounts (zero balance)...")
        specs = [
            ("NOSEXH001", "ICBC", "Industrial and Commercial Bank of China", "0180100990001",
             NostroAccount.AccountType.COLLECTION),
            ("NOSEXH002", "JPM", "JPMorgan Chase", "0001122990002",
             NostroAccount.AccountType.SETTLEMENT),
            ("NOSEXH003", "HSBC", "HSBC Holdings", "0700123990003",
             NostroAccount.AccountType.RESERVE),
        ]
        accounts = []
        for account_no, bank_code, bank_name, number, account_type in specs:
            acc, _ = NostroAccount.objects.get_or_create(
                account_no=account_no,
                defaults={
                    "bank_code": bank_code,
                    "bank_name": bank_name,
                    "account_number": encrypt_field(number),
                    "account_type": account_type,
                    "currency": "USD",
                    "balance": Decimal("0.00"),
                    "last_reconciled_balance": Decimal("0.00"),
                    "last_reconciled_at": _at(1, 18),
                    "is_active": True,
                },
            )
            acc.balance = Decimal("0.00")
            acc.last_reconciled_balance = Decimal("0.00")
            acc.save(update_fields=["balance", "last_reconciled_balance", "updated_at"])
            accounts.append(acc)
        return accounts

    def _create_deposits(self, merchant, agent, nostros):
        self.stdout.write("  Creating deposit requests...")
        collection, settlement = nostros[0], nostros[1]
        specs = [
            (merchant, None, "CUSTOMER", collection, Decimal("85000.40"), "APPROVED", 5, "Amy Fox working-capital inbound"),
            (merchant, None, "CUSTOMER", settlement, Decimal("42850.18"), "APPROVED", 3, "Prefunding Amy Fox USD VA"),
            (merchant, None, "CUSTOMER", collection, Decimal("18500.50"), "PENDING", 0, "Same-day inbound — awaiting ops review"),
            (merchant, None, "CUSTOMER", settlement, Decimal("22000.00"), "REJECTED", 2, "Name mismatch versus settlement account"),
            (None, agent, "AGENT_SELF", collection, Decimal("45000.00"), "APPROVED", 4, "Tom Lee CURRENT float top-up"),
            (None, agent, "AGENT_SELF", collection, Decimal("27500.00"), "PENDING", 0, "Agent self-fund awaiting credit"),
            (None, agent, "AGENT_SELF", settlement, Decimal("62000.00"), "APPROVED", 8, "Corridor float for customer payouts"),
            (merchant, None, "CUSTOMER", collection, Decimal("9600.00"), "PENDING", 1, "Card-rail settlement cover"),
        ]
        count = 0
        for merchant_row, agent_row, source, account, amount, status, days, remark in specs:
            created = _at(days, 9 + count, 10)
            dep = DepositRequest.objects.create(
                deposit_no=f"DEPEXH{count + 1:03d}",
                merchant=merchant_row,
                agent=agent_row,
                source=source,
                account=account,
                currency="USD",
                amount=amount,
                status=status,
                remark=remark,
                reviewed_by="admin" if status != "PENDING" else None,
                reviewed_at=created + timedelta(hours=2) if status != "PENDING" else None,
                review_comment=(
                    "Posted to collection account" if status == "APPROVED"
                    else ("Rejected — beneficiary name mismatch" if status == "REJECTED" else "")
                ),
            )
            _stamp(dep, created)
            count += 1
        self.stdout.write(f"    Deposits: {count}")
        return count

    def _create_fund_transfers(self, agent, nostros):
        self.stdout.write("  Creating nostro fund transfers...")
        collection, settlement = nostros[0], nostros[1]
        agent_current = agent.nostro_accounts.filter(
            account_type=NostroAccount.AccountType.CURRENT, currency="USD", is_deleted=False
        ).first()
        agent_fee = agent.nostro_accounts.filter(
            account_type=NostroAccount.AccountType.FEE, currency="USD", is_deleted=False
        ).first()
        specs = [
            (collection, settlement, Decimal("165000.40"), "SUCCESS", 5, "Sweep collection to settlement — T+1 payout cover"),
            (collection, settlement, Decimal("98000.75"), "SUCCESS", 3, "Mid-week liquidity sweep ICBC → JPMorgan"),
            (collection, settlement, Decimal("142500.18"), "PENDING", 0, "Same-day sweep awaiting execution"),
            (collection, nostros[2], Decimal("50000.00"), "SUCCESS", 2, "Reserve buffer HSBC"),
        ]
        if agent_current and agent_fee:
            specs.extend([
                (agent_current, agent_fee, Decimal("3200.00"), "SUCCESS", 1, "Tom Lee CURRENT → FEE commission sweep"),
                (agent_current, agent_fee, Decimal("1800.00"), "PENDING", 0, "Agent book internal transfer"),
            ])
        count = 0
        for from_acc, to_acc, amount, status, days, remark in specs:
            executed = _at(days, 16, 20)
            transfer = FundTransfer.objects.create(
                transfer_no=f"FTEXH{count + 1:03d}",
                from_account=from_acc,
                to_account=to_acc,
                amount=amount,
                currency="USD",
                status=status,
                executed_at=executed if status == "SUCCESS" else None,
                remark=remark,
            )
            _stamp(transfer, executed)
            count += 1
        self.stdout.write(f"    Fund transfers: {count}")
        return count

    def _create_bank_notifications(self, orders, nostros):
        from apps.payment.services.bank_notification import ingest_credit

        self.stdout.write("  Creating bank credit notifications...")
        paid = {
            PaymentOrder.OrderStatus.PAY_RECEIVED,
            PaymentOrder.OrderStatus.PENDING_SETTLE,
            PaymentOrder.OrderStatus.SETTLED,
            PaymentOrder.OrderStatus.REFUNDED,
            PaymentOrder.OrderStatus.REFUNDING,
        }
        created = 0
        idx = 0
        for order in orders:
            if not order.prn_code or order.status not in paid:
                continue
            if created >= 28:
                break
            bank = nostros[idx % len(nostros)]
            idx += 1
            txn_time = order.pay_received_at or order.created_at or timezone.now()
            note = ingest_credit(
                amount=order.amount,
                currency=order.from_currency or order.currency or "USD",
                remark=f"PRN:{order.prn_code}",
                prn_code=order.prn_code,
                txn_id=f"BNKEXH{order.order_no[-12:]}",
                txn_time=txn_time,
                bank_code=bank.bank_code,
                bank_name=bank.bank_name,
                account_no=bank.account_no,
                raw_payload={"source": "EXHIBITION", "order_no": order.order_no},
            )
            _stamp(note, txn_time)
            created += 1
        mismatch_src = next(
            (
                order for order in orders
                if order.status == PaymentOrder.OrderStatus.PAY_RECEIVED and order.prn_code
            ),
            None,
        )
        if mismatch_src:
            note = ingest_credit(
                amount=mismatch_src.amount + Decimal("250.00"),
                currency=mismatch_src.from_currency or "USD",
                remark=f"PRN:{mismatch_src.prn_code}",
                prn_code=mismatch_src.prn_code,
                txn_id=f"BNKEXHMIS{mismatch_src.order_no[-8:]}",
                txn_time=_at(0, 8, 20),
                bank_code=nostros[0].bank_code,
                bank_name=nostros[0].bank_name,
                account_no=nostros[0].account_no,
                raw_payload={"source": "EXHIBITION", "mismatch": True},
            )
            _stamp(note, _at(0, 8, 20))
            created += 1
        unmatched = ingest_credit(
            amount=Decimal("9100.00"),
            currency="USD",
            remark="UNMATCHED inbound — no PRN",
            prn_code="",
            txn_id="BNKEXHUNMATCH01",
            txn_time=_at(0, 7, 40),
            bank_code=nostros[0].bank_code,
            bank_name=nostros[0].bank_name,
            account_no=nostros[0].account_no,
            raw_payload={"source": "EXHIBITION", "unmatched": True},
        )
        _stamp(unmatched, _at(0, 7, 40))
        created += 1
        self.stdout.write(f"    Bank notifications: {created}")
        return created

    def _create_adjustments(self, orders):
        self.stdout.write("  Creating ledger adjustments...")
        samples = [o for o in orders if o.order_no][:8]
        specs = [
            ("amount", "pending", Decimal("250.00"), "Bank credited FX uplift of USD 250"),
            ("missing", "pending", Decimal("1800.00"), "Platform missing inbound versus statement"),
            ("amount", "approved", Decimal("125.50"), "Ops approved bank-as-source adjustment"),
            ("duplicate", "rejected", Decimal("6400.00"), "Duplicate advice — keep platform original"),
            ("status", "completed", Decimal("0.00"), "Status aligned after confirm payment"),
            ("count", "approved", Decimal("0.00"), "Item-count discrepancy closed"),
        ]
        count = 0
        for diff_type, status, amount, reason in specs:
            order = samples[count % len(samples)] if samples else None
            created = _at(count, 13, 15)
            app = AdjustmentApplication.objects.create(
                application_no=f"ADJEXH{count + 1:03d}",
                diff_type=diff_type,
                status=status,
                order_no=order.order_no if order else "",
                bank_channel="ICBC",
                amount=amount,
                currency="USD",
                reason=reason,
                adjustment_amount=amount,
                applicant="ops_analyst",
                remark="Exhibition discrepancy sample",
            )
            type(app).objects.filter(pk=app.pk).update(applied_at=created, created_at=created, updated_at=created)
            if status in ("approved", "completed", "rejected"):
                approval = AdjustmentApproval.objects.create(
                    application=app,
                    approver="admin",
                    action="approve" if status != "rejected" else "reject",
                    comment="Exhibition review",
                    level=1,
                )
                type(approval).objects.filter(pk=approval.pk).update(approved_at=created + timedelta(hours=2))
            count += 1
        self.stdout.write(f"    Adjustments: {count}")
        return count

    def _create_disbursements(self, agent):
        self.stdout.write("  Creating agent disbursements...")
        AgentDisbursementSchedule.objects.update_or_create(
            agent=agent,
            defaults={
                "enabled": True,
                "frequency": AgentDisbursementSchedule.Frequency.WEEKLY,
                "threshold_amount": Decimal("25000.00"),
                "payee_bank_name": agent.settlement_bank_name,
                "payee_account_no": agent.settlement_account_no,
                "payee_account_holder": agent.settlement_account_holder,
                "swift_code": agent.swift_code,
                "next_run_at": _at(-3, 9),
            },
        )
        specs = [
            ("PENDING_FIRST_APPROVAL", Decimal("12500.00"), 0, ""),
            ("PENDING_SECOND_APPROVAL", Decimal("8400.00"), 1, ""),
            ("SUCCESS", Decimal("22000.00"), 4, ""),
            ("REJECTED", Decimal("5100.00"), 3, "Payee name mismatch"),
            ("FAILED", Decimal("9600.00"), 2, "Correspondent timeout"),
            ("APPROVED", Decimal("4300.00"), 0, ""),
        ]
        count = 0
        for status, amount, days, fail_reason in specs:
            created = _at(days, 11, count * 7)
            row = AgentDisbursement.objects.create(
                disbursement_no=f"DBEXH{count + 1:03d}",
                agent=agent,
                currency="USD",
                amount=amount,
                payee_bank_name=agent.settlement_bank_name,
                payee_account_no=agent.settlement_account_no,
                payee_account_holder=agent.settlement_account_holder,
                swift_code=agent.swift_code,
                remark="Exhibition agent payout",
                status=status,
                fail_reason=fail_reason,
                approved_at=created + timedelta(hours=3) if status in ("APPROVED", "SUCCESS", "FAILED") else None,
                executed_at=created + timedelta(hours=5) if status in ("SUCCESS", "FAILED") else None,
            )
            _stamp(row, created)
            if status in ("PENDING_SECOND_APPROVAL", "APPROVED", "SUCCESS", "FAILED"):
                DisbursementApproval.objects.create(
                    disbursement=row,
                    step=DisbursementApproval.ApprovalStep.FIRST,
                    approver="ops_l1",
                    action=DisbursementApproval.ApprovalAction.APPROVE,
                    comment="First-pass exhibition approval",
                )
            if status in ("APPROVED", "SUCCESS", "FAILED"):
                DisbursementApproval.objects.create(
                    disbursement=row,
                    step=DisbursementApproval.ApprovalStep.SECOND,
                    approver="ops_l2",
                    action=DisbursementApproval.ApprovalAction.APPROVE,
                    comment="Second-pass exhibition approval",
                )
            if status == "REJECTED":
                DisbursementApproval.objects.create(
                    disbursement=row,
                    step=DisbursementApproval.ApprovalStep.FIRST,
                    approver="ops_l1",
                    action=DisbursementApproval.ApprovalAction.REJECT,
                    comment=fail_reason,
                )
            count += 1
        self.stdout.write(f"    Disbursements: {count}")
        return count

    def _create_scans(self, merchant, agent, orders):
        from apps.compliance.models import SanctionHitDetail, SanctionList, SanctionScanRecord

        self.stdout.write("  Creating screening records...")
        count = 0
        for target, scan_type, target_type, days in (
            (merchant, "MERCHANT_ONBOARDING", "MERCHANT", 6),
            (agent, "AGENT_ONBOARDING", "AGENT", 5),
        ):
            created = _at(days, 9, 5)
            scan = SanctionScanRecord.objects.create(
                scan_no=f"SCNEXH{count + 1:03d}",
                scan_type=scan_type,
                target_type=target_type,
                target_id=str(target.id),
                target_name=getattr(target, "merchant_name", None) or target.agent_name,
                status="CLEAR",
                hit_count=0,
                operator="seed-exhibition",
                scan_result={"matches": [], "lists": ["OFAC", "UN"]},
            )
            _stamp(scan, created)
            count += 1
        for i, order in enumerate(orders[:36], start=1):
            created = order.created_at
            scan = SanctionScanRecord.objects.create(
                scan_no=f"SCNEXHTXN{i:04d}",
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
        hit_target = orders[0] if orders else merchant
        created = _at(0, 10, 5)
        hit = SanctionScanRecord.objects.create(
            scan_no="SCNEXHHIT001",
            scan_type="TRANSACTION",
            target_type="ORDER",
            target_id=str(getattr(hit_target, "id")),
            target_name=getattr(hit_target, "beneficiary_name", None) or merchant.merchant_name,
            status="HIT",
            hit_count=1,
            operator="system",
            scan_result={"matches": [{"list": "OFAC", "score": 0.86}], "lists": ["OFAC", "UN"]},
        )
        _stamp(hit, created)
        count += 1
        entry = SanctionList.objects.filter(is_active=True).first()
        if entry:
            SanctionHitDetail.objects.create(
                scan_record=hit,
                sanction_entry=entry,
                match_field="entity_name",
                match_value=entry.entity_name,
                match_score=0.86,
                is_resolved=False,
                resolution="PENDING",
            )
        review = SanctionScanRecord.objects.create(
            scan_no="SCNEXHREV001",
            scan_type="BATCH",
            target_type="ORDER",
            target_id="batch",
            target_name="Daily beneficiary batch",
            status="MANUAL_REVIEW",
            hit_count=1,
            operator="compliance",
            scan_result={"matches": [{"list": "UN", "score": 0.61}]},
        )
        _stamp(review, _at(0, 11, 20))
        count += 1
        self.stdout.write(f"    Screening records: {count}")
        return count

    def _create_reconciliation(self, nostros, orders):
        from apps.reconciliation.models import NostroBalanceCheck, ReconAlert, ReconciliationBatch, ReconciliationDiff

        self.stdout.write("  Creating reconciliation batches...")
        banks = [
            ("ICBC", "Industrial and Commercial Bank of China"),
            ("JPM", "JPMorgan Chase"),
        ]
        batch_count = 0
        for days_ago in range(4, 0, -1):
            recon_date = timezone.localdate() - timedelta(days=days_ago)
            started = _at(days_ago, 22, 15)
            completed = started + timedelta(minutes=42)
            for bank_code, bank_name in banks:
                day_orders = [
                    o for o in orders
                    if o.pay_received_at and timezone.localtime(o.pay_received_at).date() == recon_date
                ]
                platform_count = len(day_orders)
                platform_amount = sum((o.amount for o in day_orders), Decimal("0"))
                is_diff = days_ago == 1 and bank_code == "ICBC"
                extra = Decimal("21500.40") if is_diff else Decimal("0")
                bank_count = platform_count + (1 if is_diff else 0)
                bank_amount = platform_amount + extra
                match_count = max(platform_count - (1 if is_diff else 0), 0)
                match_amount = platform_amount
                if is_diff and day_orders:
                    match_amount = max(platform_amount - day_orders[0].amount, Decimal("0"))
                batch = ReconciliationBatch.objects.create(
                    batch_no=f"RECONEXH{recon_date.strftime('%Y%m%d')}{bank_code}",
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
                            bank_txn_id=sample.order_no,
                            txn_time=sample.pay_received_at,
                            amount_bank=sample.amount + Decimal("250.00"),
                            amount_platform=sample.amount,
                            resolution=ReconciliationDiff.ResolutionType.ADJUST_PLATFORM,
                            resolution_note="Bank credited FX uplift of USD 250",
                            resolved_by="admin",
                            resolved_at=completed,
                        )
                    ReconAlert.objects.create(
                        batch=batch,
                        severity=ReconAlert.Severity.WARNING,
                        title="ICBC statement has unmatched credits",
                        summary="Exhibition recon found bank-only items on T-1.",
                        channel=ReconAlert.Channel.IN_APP,
                        status=ReconAlert.AlertStatus.OPEN,
                        sent_at=completed,
                    )
        for acc in nostros[:2]:
            platform_bal = acc.balance
            bank_bal = platform_bal + random.choice([Decimal("0"), Decimal("-1250"), Decimal("3200")])
            NostroBalanceCheck.objects.create(
                check_date=timezone.localdate() - timedelta(days=1),
                nostro_account=acc,
                platform_balance=platform_bal,
                bank_statement_balance=bank_bal,
                difference=bank_bal - platform_bal,
                is_balanced=(bank_bal == platform_bal),
                remark="Auto-matched" if bank_bal == platform_bal else "Immaterial difference — next cycle",
            )
        self.stdout.write(f"    Reconciliation batches: {batch_count}")
        return batch_count

    def _create_pending_onboarding(self):
        self.stdout.write("  Creating pending KYC queue users...")
        specs = [
            {
                "username": "ChrisPark",
                "email": "chrispark@gmail.com",
                "phone": "254700300003",
                "name": "Chris Park",
                "role": "merchant",
                "industry": "Industrial equipment import",
            },
            {
                "username": "SarahKim",
                "email": "sarahkim@gmail.com",
                "phone": "254700400004",
                "name": "Sarah Kim",
                "role": "agent",
                "industry": "Regional collection agency",
            },
        ]
        count = 0
        for spec in specs:
            user = EndUser.objects.create(
                username=spec["username"],
                phone=spec["phone"],
                email=spec["email"],
                password_hash=_hash_password(PASSWORD),
                nickname=spec["name"],
                real_name=spec["name"],
                is_verified=False,
                portal_role=spec["role"],
                onboarding_status="pending",
                onboarding_submitted_at=_at(1, 15),
            )
            UserOnboarding.objects.create(
                user=user,
                legal_name=spec["name"],
                id_type=UserOnboarding.IdType.PASSPORT,
                id_number=f"A{spec['phone'][-8:]}",
                contact_phone=spec["phone"],
                nationality="Kenya",
                address="Nairobi, Kenya",
                license_expiry_date=_at(-400, 10).date(),
                bank_name="Equity Bank Kenya",
                branch_name="Westlands Branch",
                account_name=f"{spec['name']} Ltd",
                bank_account=f"0180{spec['phone'][-6:]}",
                swift_code="EQBLKENA",
                agent_review_status=UserOnboarding.AgentReviewStatus.NONE,
                application_ref=f"KYB-{spec['username'].upper()}",
                kyb_payload={
                    "application_ref": f"KYB-{spec['username'].upper()}",
                    "region": "KE",
                    "currency": "USD",
                    "account_type": "BUSINESS",
                    "market": {"name": "Kenya", "registry": "BRS", "tax_label": "PIN"},
                    "business": {
                        "legal_name": f"{spec['name']} Ltd",
                        "trading_name": spec["name"],
                        "industry": spec["industry"],
                        "tax_id": f"P{spec['phone'][-8:]}",
                        "email": spec["email"],
                        "phone": spec["phone"],
                        "address": "Nairobi, Kenya",
                    },
                    "people": [{"role": "Director", "name": spec["name"], "ownership_pct": 100, "pep": False}],
                    "payout": {
                        "method": "WIRE",
                        "bank_name": "Equity Bank Kenya",
                        "account_number": f"0180{spec['phone'][-6:]}",
                    },
                },
            )
            count += 1
        return count

    def _create_daily_reports(self):
        from apps.report.tasks import generate_daily_reports

        self.stdout.write("  Generating daily report snapshots...")
        for days_ago in range(6, -1, -1):
            generate_daily_reports(timezone.localdate() - timedelta(days=days_ago))

