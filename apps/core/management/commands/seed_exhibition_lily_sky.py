"""Seed exhibition demo data for the Lily Sky merchant portal account.

Usage:
    python manage.py seed_exhibition_lily_sky
"""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.account.models import UserAccount, UserPaymentDetail, VaLedgerEntry, VirtualAccount
from apps.core.utils import encrypt_field, generate_idempotency_key
from apps.merchant.models import Merchant, MerchantSettlementAccount
from apps.merchant.services import ensure_merchant_multi_currency_accounts
from apps.payment.models import PaymentOrder
from apps.payment.services.prn_service import generate_prn
from apps.user_portal.models import EndUser, UserOnboarding


EXHIBITION_EMAIL = "lilysky@qq.com"

# CapitalPay deposit book shown on Accounts / Bank.
VA_BALANCES = {
    "USD": Decimal("128450.00"),
    "EUR": Decimal("46200.50"),
    "CNY": Decimal("890000.00"),
    "HKD": Decimal("215000.00"),
}


def _at(days_ago, hour, minute):
    base = timezone.localdate() - timedelta(days=days_ago)
    return timezone.make_aware(datetime.combine(base, time(hour, minute)))


def _stamp(obj, dt):
    type(obj).objects.filter(pk=obj.pk).update(created_at=dt, updated_at=dt)


class Command(BaseCommand):
    help = "Load exhibition balances, ledger and remittance samples for Lily Sky"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            default=EXHIBITION_EMAIL,
            help="Merchant portal login email (default: lilysky@qq.com)",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        email = (options["email"] or "").strip().lower()
        user = EndUser.objects.filter(email__iexact=email, is_deleted=False).first()
        if not user:
            raise CommandError(f"Merchant portal user not found for email={email}")
        merchant = user.default_merchant
        if not merchant:
            raise CommandError(f"User {email} has no linked merchant")

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Seeding exhibition data for {merchant.merchant_name} ({email})..."
        ))

        self._polish_profile(user, merchant)
        ensure_merchant_multi_currency_accounts(merchant)
        self._set_va_balances(merchant)
        self._ensure_bound_accounts(user, merchant)
        orders = self._ensure_orders(user, merchant)
        ledger_count = self._rebuild_ledger(merchant, orders)
        payment_details = self._ensure_payment_details(user, orders)

        self.stdout.write(self.style.SUCCESS("Exhibition seed complete"))
        self.stdout.write(f"  Merchant: {merchant.merchant_no} {merchant.merchant_name}")
        self.stdout.write(f"  VA books: {', '.join(f'{c} {a}' for c, a in VA_BALANCES.items())}")
        self.stdout.write(f"  Remittance samples: {len(orders)}")
        self.stdout.write(f"  VA ledger entries: {ledger_count}")
        self.stdout.write(f"  Payment details: {payment_details}")
        self.stdout.write(f"  Login: {email}  (existing password)")

    def _polish_profile(self, user, merchant):
        merchant.short_name = merchant.short_name or "Lily Sky"
        merchant.contact_name = merchant.contact_name or user.real_name or "Lily Sky"
        merchant.contact_email = merchant.contact_email or user.email
        if merchant.status != Merchant.Status.ACTIVE:
            merchant.status = Merchant.Status.ACTIVE
        merchant.save()

        onboarding = UserOnboarding.objects.filter(user=user).first()
        if onboarding:
            onboarding.legal_name = onboarding.legal_name or "Lily Sky"
            onboarding.account_name = "Lily Sky Trading Ltd"
            onboarding.bank_name = "Equity Bank Kenya"
            onboarding.branch_name = "Westlands Branch"
            onboarding.bank_account = onboarding.bank_account if onboarding.bank_account not in ("", "Lily Sky") else "0180555012345"
            onboarding.swift_code = onboarding.swift_code or "EQBLKENA"
            onboarding.nationality = onboarding.nationality or "Kenya"
            onboarding.address = onboarding.address or "Westlands, Nairobi, Kenya"
            onboarding.save()

        settlement = (
            MerchantSettlementAccount.objects.filter(merchant=merchant, is_deleted=False)
            .order_by("-is_default", "-created_at")
            .first()
        )
        if settlement:
            settlement.bank_name = "Equity Bank Kenya"
            settlement.bank_branch = "Westlands Branch, Nairobi"
            settlement.account_name = "Lily Sky Trading Ltd"
            settlement.account_number = encrypt_field("0180555012345")
            settlement.is_default = True
            settlement.save()
        else:
            MerchantSettlementAccount.objects.create(
                merchant=merchant,
                bank_name="Equity Bank Kenya",
                bank_branch="Westlands Branch, Nairobi",
                account_name="Lily Sky Trading Ltd",
                account_number=encrypt_field("0180555012345"),
                is_default=True,
            )

    def _set_va_balances(self, merchant):
        for currency, amount in VA_BALANCES.items():
            va = VirtualAccount.objects.filter(
                merchant=merchant, currency=currency, is_deleted=False
            ).first()
            if not va:
                continue
            va.ledger_balance = amount
            va.available_balance = amount
            va.status = VirtualAccount.VaStatus.ACTIVE
            va.save(update_fields=["ledger_balance", "available_balance", "status", "updated_at"])
            self.stdout.write(f"  VA {currency}: {amount}")

    def _ensure_bound_accounts(self, user, merchant):
        specs = [
            ("EQBL", "Equity Bank Kenya", "Lily Sky Trading Ltd", "0180555012345", "EQBLKENA"),
            ("HSBC", "HSBC Holdings", "Lily Sky Trading Ltd", "0100888123456", "HSBCHKHH"),
        ]
        existing = {
            row.bank_code: row
            for row in UserAccount.objects.filter(user_id=str(user.id), is_deleted=False)
        }
        for bank_code, bank_name, holder, number, _swift in specs:
            if bank_code in existing:
                continue
            UserAccount.objects.create(
                user_id=str(user.id),
                merchant=merchant,
                bank_code=bank_code,
                bank_name=bank_name,
                account_holder=holder,
                account_number=encrypt_field(number),
                bind_token=encrypt_field(f"token_lily_{bank_code.lower()}"),
                status=UserAccount.BindStatus.ACTIVE,
                bind_at=timezone.now() - timedelta(days=20),
            )
            self.stdout.write(f"  Bound account: {bank_name}")

    def _ensure_orders(self, user, merchant):
        """Idempotent exhibition remittances tagged with LILYSKY order numbers."""
        specs = [
            # days, amount, from_ccy, to_ccy, pay_method, status, beneficiary, bank, swift, account, purpose
            (5, Decimal("25000.00"), "USD", "EUR", "WIRE_TRANSFER", PaymentOrder.OrderStatus.SETTLED,
             "Siemens AG", "COMMERZBANK AG", "COBADEFF", "DE89370400440532013000",
             "Exhibition: settled wire remittance"),
            (4, Decimal("18500.00"), "USD", "CNY", "WALLET", PaymentOrder.OrderStatus.SETTLED,
             "Huawei Technologies", "Bank of China", "BKCHCNBJ", "778812340001",
             "Exhibition: settled wallet funding"),
            (3, Decimal("9200.00"), "USD", "EUR", "CARD", PaymentOrder.OrderStatus.PAY_RECEIVED,
             "Schneider Electric", "BNP PARIBAS", "BNPAFRPP", "FR1420041010050500013M02606",
             "Exhibition: card funding received"),
            (2, Decimal("15600.00"), "USD", "GBP", "WIRE_TRANSFER", PaymentOrder.OrderStatus.PENDING_SETTLE,
             "Unilever PLC", "Barclays Bank", "BARCGB22", "GB29NWBK60161331926819",
             "Exhibition: payout in progress"),
            (1, Decimal("11200.50"), "USD", "EUR", "WALLET", PaymentOrder.OrderStatus.PENDING_REVIEW,
             "ABB Ltd", "UBS Switzerland", "UBSWCHZH", "CH9300762011623852957",
             "Exhibition: pending CapitalPay review"),
            (0, Decimal("7800.00"), "USD", "HKD", "CARD", PaymentOrder.OrderStatus.PENDING_REVIEW,
             "Li & Fung Ltd", "HSBC Hong Kong", "HSBCHKHH", "HK123456789012",
             "Exhibition: card funding under review"),
        ]

        orders = []
        for idx, (days, amount, from_ccy, to_ccy, pay_method, status, bene, bank, swift, acct, purpose) in enumerate(specs, start=1):
            order_no = f"PAYLILYSKY{idx:02d}"
            existing = PaymentOrder.objects.filter(order_no=order_no).first()
            if existing:
                orders.append(existing)
                continue

            fee = max((amount * Decimal("0.003")).quantize(Decimal("0.01")), Decimal("10.00"))
            created = _at(days, 10 + idx, 15)
            history = [{"status": "PENDING_REVIEW", "time": created.isoformat()}]
            pay_received_at = None
            settled_at = None
            prn_code = None

            if status in (
                PaymentOrder.OrderStatus.PAY_RECEIVED,
                PaymentOrder.OrderStatus.PENDING_SETTLE,
                PaymentOrder.OrderStatus.SETTLED,
            ):
                prn_code = generate_prn(agent=None, on_date=timezone.localdate() - timedelta(days=days))
                pay_at = created + timedelta(hours=3)
                history.append({"status": "PAY_RECEIVED", "time": pay_at.isoformat()})
                pay_received_at = pay_at
            if status == PaymentOrder.OrderStatus.PENDING_SETTLE:
                history.append({"status": "PENDING_SETTLE", "time": (created + timedelta(hours=5)).isoformat()})
            if status == PaymentOrder.OrderStatus.SETTLED:
                settled_at = created + timedelta(days=1, hours=2)
                history.append({"status": "PENDING_SETTLE", "time": (created + timedelta(hours=5)).isoformat()})
                history.append({"status": "SETTLED", "time": settled_at.isoformat()})

            order = PaymentOrder.objects.create(
                order_no=order_no,
                merchant_order_no=f"LS-EXH-{idx:02d}",
                unique_identification_no=f"UINLILYSKY{idx:02d}",
                prn_code=prn_code,
                merchant=merchant,
                user_id=str(user.id),
                currency=from_ccy,
                amount=amount,
                fee_amount=fee,
                settle_amount=amount - fee,
                sender_total_amount=amount + fee,
                fee_currency=from_ccy,
                from_currency=from_ccy,
                to_currency=to_ccy,
                fee_bearing="OUR",
                beneficiary_name=bene,
                beneficiary_bank=bank,
                beneficiary_swift=swift,
                beneficiary_account=acct,
                beneficiary_address="Exhibition beneficiary address",
                remittance_purpose=purpose,
                pay_method=pay_method,
                bank_code="EQBL" if pay_method == "WIRE_TRANSFER" else "",
                status=status,
                agent_review_status=PaymentOrder.AgentReviewStatus.NONE,
                pay_received_at=pay_received_at,
                settled_at=settled_at,
                status_history=history,
                expire_at=created + timedelta(days=3),
                idempotency_key=generate_idempotency_key(f"exh_lily_{idx}_"),
            )
            _stamp(order, created)
            orders.append(order)
            self.stdout.write(f"  Order {order_no}: {status} {amount} {from_ccy} via {pay_method}")

        return orders

    def _rebuild_ledger(self, merchant, orders):
        """Rebuild USD VA activity from exhibition orders; keep configured book balances."""
        va = VirtualAccount.objects.filter(
            merchant=merchant, currency="USD", is_deleted=False
        ).first()
        if not va:
            return 0

        VaLedgerEntry.objects.filter(virtual_account=va, source_id__startswith="exh-lily-").delete()
        VaLedgerEntry.objects.filter(virtual_account=va, order_id__in=[o.id for o in orders]).delete()

        received = {
            PaymentOrder.OrderStatus.PAY_RECEIVED,
            PaymentOrder.OrderStatus.PENDING_PAY,
            PaymentOrder.OrderStatus.SETTLED,
            PaymentOrder.OrderStatus.PENDING_SETTLE,
        }
        # Walk credits chronologically then pin final balance to exhibition target.
        running = Decimal("0.00")
        count = 0
        for order in sorted(
            [o for o in orders if o.status in received],
            key=lambda o: o.pay_received_at or o.created_at,
        ):
            occurred = order.pay_received_at or order.created_at
            running += order.amount
            entry = VaLedgerEntry.objects.create(
                virtual_account=va,
                order=order,
                entry_type=VaLedgerEntry.EntryType.CREDIT,
                amount=order.amount,
                balance_after=running,
                source_type="PAYMENT",
                source_id=f"exh-lily-{order.order_no}",
                remark=f"Collection confirmed {order.order_no}",
            )
            _stamp(entry, occurred)
            count += 1
            if order.status == PaymentOrder.OrderStatus.SETTLED and order.settled_at:
                running -= order.settle_amount
                debit = VaLedgerEntry.objects.create(
                    virtual_account=va,
                    order=order,
                    entry_type=VaLedgerEntry.EntryType.DEBIT,
                    amount=order.settle_amount,
                    balance_after=running,
                    source_type="SETTLEMENT",
                    source_id=f"exh-lily-settle-{order.order_no}",
                    remark=f"Settlement payout {order.order_no}",
                )
                _stamp(debit, order.settled_at)
                count += 1

        # Keep the exhibition headline balances (not the reconstructed running total).
        target = VA_BALANCES.get("USD", running)
        va.ledger_balance = target
        va.available_balance = target
        va.save(update_fields=["ledger_balance", "available_balance", "updated_at"])
        return count

    def _ensure_payment_details(self, user, orders):
        count = 0
        for order in orders:
            if order.status in (
                PaymentOrder.OrderStatus.PENDING_REVIEW,
                PaymentOrder.OrderStatus.CLOSED,
            ):
                continue
            exists = UserPaymentDetail.objects.filter(
                user_id=str(user.id), order=order, is_deleted=False
            ).exists()
            if exists:
                continue
            UserPaymentDetail.objects.create(
                user_id=str(user.id),
                order=order,
                account=None,
                pay_method=order.pay_method,
                amount=order.amount,
                pay_time=order.pay_received_at or order.created_at,
            )
            count += 1
        return count
