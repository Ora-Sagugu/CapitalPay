"""种子数据命令 — 一键填充 demo 数据。

用法:
    python manage.py seed_data
    python manage.py seed_data --reset   # 先清空再填充
"""
import hashlib
import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.utils import encrypt_field, generate_idempotency_key
from apps.merchant.models import (
    Merchant, MerchantKYC, MerchantFee, MerchantSettlementAccount, MerchantPaymentProduct,
)
from apps.payment.models import PaymentOrder, RefundOrder
from apps.account.models import NostroAccount, UserAccount, FundTransfer
from apps.reconciliation.models import ReconciliationBatch, ReconciliationDiff, NostroBalanceCheck
from apps.settlement.models import SettlementBatch, SettlementDetail, FeeShare, DifferenceWriteOff
from apps.routing.models import BankChannel, BankTransaction


def _days_ago(n):
    return timezone.now() - timedelta(days=n)


def _hours_ago(n):
    return timezone.now() - timedelta(hours=n)


class Command(BaseCommand):
    help = "填充 B2B 支付系统演示数据"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="先清空现有数据再填充")

    def handle(self, *args, **options):
        if options["reset"]:
            self._reset_data()

        self.stdout.write(self.style.MIGRATE_HEADING("开始填充种子数据..."))

        merchants = self._create_merchants()
        nostro_accounts = self._create_nostro_accounts()
        self._create_bank_channels()
        orders = self._create_payment_orders(merchants)
        self._create_refunds(orders)
        self._create_reconciliation(nostro_accounts)
        self._create_settlement(merchants, orders)
        self._create_rbac_data()
        self._create_user_portal_data(merchants, orders)

        self.stdout.write(self.style.SUCCESS("\n种子数据填充完成!"))
        self.stdout.write("  商户: 3 家 (含 KYC、手续费、结算账户)")
        self.stdout.write("  Nostro 账户: 3 个")
        self.stdout.write("  银行通道: 6 个 (含演示流水)")
        self.stdout.write("  支付订单: 12 笔 (覆盖各种状态)")
        self.stdout.write("  退款单: 2 笔")
        self.stdout.write("  对账批次: 2 批 (含差异记录)")
        self.stdout.write("  清算批次: 2 批 (含明细和分润)")
        self.stdout.write("  Nostro 余额核对: 3 条")
        self.stdout.write("  RBAC: 28 个权限 + 7 个角色 + 5 个运营账号")
        self.stdout.write("  用户端: 6 个终端用户 + 用户支付明细 + 账户绑定")

    # ── 清空 ──────────────────────────────────────────────

    def _reset_data(self):
        self.stdout.write(self.style.WARNING("清空现有数据..."))
        for model in [
            DifferenceWriteOff, FeeShare, SettlementDetail, SettlementBatch,
            NostroBalanceCheck, ReconciliationDiff, ReconciliationBatch,
            FundTransfer, UserAccount, NostroAccount,
            RefundOrder, PaymentOrder,
            BankTransaction, BankChannel,
            MerchantPaymentProduct, MerchantSettlementAccount, MerchantFee, MerchantKYC, Merchant,
        ]:
            model.objects.all().delete()
        # RBAC 和 用户端
        from apps.rbac.models import SystemUser, Role, Permission, UserRole, RolePermission, OperationLog
        from apps.user_portal.models import EndUser, SmsCode, RefreshToken
        for model in [UserRole, RolePermission, OperationLog, SystemUser, Role, Permission,
                      RefreshToken, SmsCode, EndUser]:
            model.objects.all().delete()
        self.stdout.write("  已清空")

    # ── 商户 ──────────────────────────────────────────────

    def _create_merchants(self):
        self.stdout.write("  创建商户...")
        merchants = []

        m1 = Merchant.objects.create(
            merchant_no="M20260001",
            merchant_name="深圳市环球贸易有限公司",
            short_name="环球贸易",
            status=Merchant.Status.ACTIVE,
            contact_name="张伟",
            contact_phone="13800138001",
            contact_email="zhangwei@hq-trade.com",
            api_key="ak_hq_trade_001",
            api_secret="sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
        )
        MerchantKYC.objects.create(
            merchant=m1,
            legal_person="张伟",
            id_number=encrypt_field("440301199001011234"),
            business_license=encrypt_field("91440300700123456X"),
            business_scope="电子产品、通讯设备、计算机软硬件的技术开发与销售；国内贸易；货物及技术进出口。",
            registered_capital=Decimal("5000000"),
            established_date=_days_ago(365 * 8).date(),
            registered_address="深圳市南山区科技园南区",
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
            bank_name="招商银行",
            bank_branch="深圳高新园支行",
            account_name="深圳市环球贸易有限公司",
            account_number=encrypt_field("6225880123456789"),
            is_default=True,
        )
        MerchantPaymentProduct.objects.create(
            merchant=m1,
            product_type="WIRE_TRANSFER",
            is_enabled=True,
            max_single_amount=Decimal("5000000"),
            daily_limit=Decimal("20000000"),
        )
        merchants.append(m1)

        m2 = Merchant.objects.create(
            merchant_no="M20260002",
            merchant_name="北京北方建材集团有限公司",
            short_name="北方建材",
            status=Merchant.Status.ACTIVE,
            contact_name="李娜",
            contact_phone="13900139002",
            contact_email="lina@bf-build.com",
            api_key="ak_bf_build_002",
            api_secret="sk_q7w8e9r0t1y2u3i4o5p6a7s8d9f0g1h2",
        )
        MerchantKYC.objects.create(
            merchant=m2,
            legal_person="李娜",
            id_number=encrypt_field("110108198503156789"),
            business_license=encrypt_field("91110108700245678X"),
            business_scope="建筑材料、装饰材料、金属材料、五金交电的销售；建筑工程施工。",
            registered_capital=Decimal("10000000"),
            established_date=_days_ago(365 * 12).date(),
            registered_address="北京市海淀区中关村大街",
        )
        MerchantFee.objects.create(
            merchant=m2,
            product_type=MerchantFee.ProductType.WIRE_TRANSFER,
            fee_model=MerchantFee.FeeModel.PERCENTAGE,
            fee_rate=Decimal("0.0025"),
            min_fee=Decimal("20.00"),
            max_fee=Decimal("800.00"),
            effective_from=_days_ago(90).date(),
        )
        MerchantSettlementAccount.objects.create(
            merchant=m2,
            bank_name="中国工商银行",
            bank_branch="北京海淀支行",
            account_name="北京北方建材集团有限公司",
            account_number=encrypt_field("0200001019200367890"),
            is_default=True,
        )
        merchants.append(m2)

        m3 = Merchant.objects.create(
            merchant_no="M20260003",
            merchant_name="上海数字未来科技有限公司",
            short_name="数字未来",
            status=Merchant.Status.SUSPENDED,
            contact_name="王强",
            contact_phone="13700137003",
            contact_email="wangqiang@digital-future.com",
            api_key="ak_digital_003",
            api_secret="sk_z3x4c5v6b7n8m9a1q2w3e4r5t6y7u8i9",
        )
        MerchantKYC.objects.create(
            merchant=m3,
            legal_person="王强",
            id_number=encrypt_field("310104199207084567"),
            business_license=encrypt_field("91310104700456789X"),
            business_scope="计算机软硬件开发；信息技术服务；数据处理与存储服务。",
            registered_capital=Decimal("3000000"),
            established_date=_days_ago(365 * 5).date(),
            registered_address="上海市浦东新区张江高科技园区",
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
            bank_name="中国建设银行",
            bank_branch="上海张江支行",
            account_name="上海数字未来科技有限公司",
            account_number=encrypt_field("31001501205050001234"),
            is_default=True,
        )
        merchants.append(m3)

        self.stdout.write(f"    完成: {len(merchants)} 家商户")
        return merchants

    # ── Nostro 账户 ──────────────────────────────────────

    def _create_nostro_accounts(self):
        self.stdout.write("  创建 Nostro 账户...")
        accounts = []

        a1 = NostroAccount.objects.create(
            account_no="NOS20260001",
            bank_code="CMB",
            bank_name="招商银行",
            account_number=encrypt_field("755901234510902"),
            account_type=NostroAccount.AccountType.COLLECTION,
            balance=Decimal("8520000.00"),
            last_reconciled_balance=Decimal("8500000.00"),
            last_reconciled_at=_hours_ago(12),
        )
        accounts.append(a1)

        a2 = NostroAccount.objects.create(
            account_no="NOS20260002",
            bank_code="ICBC",
            bank_name="中国工商银行",
            account_number=encrypt_field("0200001019200367890"),
            account_type=NostroAccount.AccountType.SETTLEMENT,
            balance=Decimal("3200000.00"),
            last_reconciled_balance=Decimal("3200000.00"),
            last_reconciled_at=_hours_ago(12),
        )
        accounts.append(a2)

        a3 = NostroAccount.objects.create(
            account_no="NOS20260003",
            bank_code="CCB",
            bank_name="中国建设银行",
            account_number=encrypt_field("31001501205050001234"),
            account_type=NostroAccount.AccountType.RESERVE,
            balance=Decimal("5000000.00"),
        )
        accounts.append(a3)

        # 资金调拨记录
        FundTransfer.objects.create(
            transfer_no="FT20260705001",
            from_account=a1,
            to_account=a2,
            amount=Decimal("500000.00"),
            status=FundTransfer.TransferStatus.SUCCESS,
            executed_at=_hours_ago(24),
            remark="收款账户到结算账户调拨",
        )

        self.stdout.write(f"    完成: {len(accounts)} 个 Nostro 账户")
        return accounts

    # ── 银行通道 ──────────────────────────────────────────

    def _create_bank_channels(self):
        self.stdout.write("  创建银行通道...")
        banks = [
            {"bank_code": "HSBC", "bank_name": "HSBC", "country": "Hong Kong, China",
             "channel_type": "online", "status": "active", "priority": 100,
             "fee_rate": "0.0010", "min_fee": "2.00", "max_fee": "500.00",
             "usd_balance": "5000000", "hkd_balance": "8000000", "cny_balance": "3000000",
             "supported_currencies": ["USD", "HKD", "CNY", "EUR"],
             "supported_countries": ["CN", "HK", "US", "GB"]},
            {"bank_code": "SCBL", "bank_name": "Standard Chartered Bank", "country": "United Kingdom",
             "channel_type": "wire", "status": "active", "priority": 90,
             "fee_rate": "0.0015", "min_fee": "5.00", "max_fee": "800.00",
             "usd_balance": "3000000", "hkd_balance": "5000000", "cny_balance": "1000000",
             "supported_currencies": ["USD", "HKD", "CNY", "GBP"],
             "supported_countries": ["CN", "HK", "GB", "US"]},
            {"bank_code": "BKCH", "bank_name": "Bank of China", "country": "China",
             "channel_type": "realtime", "status": "active", "priority": 95,
             "fee_rate": "0.0008", "min_fee": "1.00", "max_fee": "300.00",
             "usd_balance": "8000000", "hkd_balance": "3000000", "cny_balance": "50000000",
             "supported_currencies": ["CNY", "USD", "HKD", "EUR", "JPY"],
             "supported_countries": ["CN", "HK", "US"]},
            {"bank_code": "ICBC", "bank_name": "ICBC", "country": "China",
             "channel_type": "online", "status": "active", "priority": 88,
             "fee_rate": "0.0009", "min_fee": "1.50", "max_fee": "400.00",
             "usd_balance": "6000000", "hkd_balance": "2000000", "cny_balance": "45000000",
             "supported_currencies": ["CNY", "USD", "HKD"],
             "supported_countries": ["CN", "HK"]},
            {"bank_code": "JPMO", "bank_name": "JPMorgan Chase", "country": "United States",
             "channel_type": "ach", "status": "suspended", "priority": 70,
             "fee_rate": "0.0020", "min_fee": "10.00", "max_fee": "1000.00",
             "usd_balance": "10000000", "hkd_balance": "0", "cny_balance": "0",
             "supported_currencies": ["USD", "EUR"],
             "supported_countries": ["US", "GB"]},
            {"bank_code": "CITI", "bank_name": "Citibank", "country": "United States",
             "channel_type": "wire", "status": "maintenance", "priority": 80,
             "fee_rate": "0.0018", "min_fee": "8.00", "max_fee": "900.00",
             "usd_balance": "4500000", "hkd_balance": "1500000", "cny_balance": "2000000",
             "supported_currencies": ["USD", "HKD", "CNY"],
             "supported_countries": ["US", "CN", "HK"]},
        ]
        for b in banks:
            BankChannel.objects.create(**b)

        names = [
            "Zhang Wei", "Li Na", "WONG Chi Ming", "John Smith", "Maria Garcia",
            "Chen Fang", "LI Ka Shing", "David Chen", "Wang Lei", "Alice Wang",
        ]
        currencies = ["USD", "HKD", "CNY"]
        now = timezone.now()
        txn_count = 0
        for bank in BankChannel.objects.all():
            for _ in range(random.randint(8, 15)):
                cur = random.choice(currencies)
                amt = round(random.uniform(500, 50000), 2)
                fee = round(amt * float(bank.fee_rate), 2)
                fee = max(fee, float(bank.min_fee))
                fee = min(fee, float(bank.max_fee))
                bal = float(getattr(bank, f"{cur.lower()}_balance"))
                d = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
                BankTransaction.objects.create(
                    bank=bank,
                    txn_date=d,
                    prn=f"PRN{random.randint(100000, 999999)}",
                    beneficiary_name=random.choice(names),
                    amount=amt,
                    currency=cur,
                    fee=fee,
                    balance=round(bal - amt, 2),
                )
                txn_count += 1

        self.stdout.write(f"    完成: {len(banks)} 个通道, {txn_count} 笔流水")

    # ── 支付订单 ──────────────────────────────────────────

    def _create_payment_orders(self, merchants):
        self.stdout.write("  创建支付订单...")
        m1, m2, m3 = merchants
        orders = []

        scenarios = [
            # (merchant, amount, pay_method, status, days_ago, bank_code, bank_txn_id)
            (m1, Decimal("500000.00"), "WIRE_TRANSFER", "SETTLED", 15, "CMB", "CMB20260620001"),
            (m1, Decimal("120000.00"), "WIRE_TRANSFER", "SETTLED", 10, "CMB", "CMB20260625002"),
            (m1, Decimal("88000.00"), "ONLINE_BANK", "SETTLED", 8, "CMB", "CMB20260627003"),
            (m1, Decimal("350000.00"), "WIRE_TRANSFER", "PENDING_SETTLE", 3, "CMB", "CMB20260701004"),
            (m1, Decimal("67000.00"), "WIRE_TRANSFER", "PAY_RECEIVED", 2, "CMB", "CMB20260702005"),
            (m1, Decimal("450000.00"), "WIRE_TRANSFER", "PENDING_PAY", 1, "CMB", None),
            (m1, Decimal("99000.00"), "ONLINE_BANK", "CLOSED", 5, "CMB", None),
            (m1, Decimal("150000.00"), "WIRE_TRANSFER", "PRE_CREATE", 0, "CMB", None),
            (m2, Decimal("800000.00"), "WIRE_TRANSFER", "SETTLED", 12, "ICBC", "ICBC20260622006"),
            (m2, Decimal("230000.00"), "WIRE_TRANSFER", "PENDING_SETTLE", 4, "ICBC", "ICBC20260701007"),
            (m2, Decimal("50000.00"), "AUTHORIZED", "REFUNDED", 6, "ICBC", "ICBC20260626008"),
            (m3, Decimal("15000.00"), "AUTHORIZED", "PAY_RECEIVED", 1, "CCB", "CCB20260702009"),
        ]

        for i, (merch, amount, method, status, days, bank_code, bank_txn) in enumerate(scenarios):
            created = _days_ago(days)
            expire = created + timedelta(hours=24)

            fee = self._calc_fee(merch, amount)
            settle = amount - fee

            order = PaymentOrder.objects.create(
                order_no=f"PAY2026070{i+10:04d}",
                merchant_order_no=f"M{merch.merchant_no[-4:]}{i+1:04d}",
                unique_identification_no=f"UIN2026070{i+10:04d}",
                merchant=merch,
                user_id=f"U{random.randint(1000, 9999)}",
                currency="CNY",
                amount=amount,
                fee_amount=fee,
                settle_amount=settle,
                pay_method=method,
                bank_code=bank_code,
                bank_txn_id=bank_txn,
                status=status,
                status_history=[
                    {"status": "PRE_CREATE", "time": created.isoformat()},
                    {"status": "PENDING_PAY", "time": (created + timedelta(minutes=1)).isoformat()},
                ],
                pay_received_at=(created + timedelta(hours=2)) if status not in ("PRE_CREATE", "PENDING_PAY", "CLOSED") else None,
                settled_at=(created + timedelta(hours=48)) if status == "SETTLED" else None,
                closed_at=(created + timedelta(hours=24)) if status == "CLOSED" else None,
                expire_at=expire,
                idempotency_key=generate_idempotency_key("seed_"),
                notify_url="https://demo.merchant.com/callback",
                notify_status="SUCCESS" if status in ("SETTLED", "PAY_RECEIVED", "PENDING_SETTLE") else "PENDING",
            )
            orders.append(order)

        self.stdout.write(f"    完成: {len(orders)} 笔订单")
        return orders

    def _calc_fee(self, merchant, amount):
        """简单计算手续费。"""
        for fee in merchant.fees.all():
            if fee.fee_model == "PERCENTAGE":
                calc = amount * fee.fee_rate
                if calc < fee.min_fee:
                    return fee.min_fee
                if fee.max_fee and calc > fee.max_fee:
                    return fee.max_fee
                return calc.quantize(Decimal("0.01"))
            elif fee.fee_model == "FIXED":
                return fee.fixed_fee
        return Decimal("0.00")

    # ── 退款 ──────────────────────────────────────────────

    def _create_refunds(self, orders):
        self.stdout.write("  创建退款单...")
        # 找到已退款的订单
        refund_orders = [o for o in orders if o.status == "REFUNDED"]
        refunds_created = 0

        for order in refund_orders:
            RefundOrder.objects.create(
                refund_no=f"RF{order.order_no[3:]}",
                payment_order=order,
                refund_amount=order.amount,
                refund_reason="商品质量问题，全额退款",
                status=RefundOrder.RefundStatus.SUCCESS,
                reviewed_by="admin",
                reviewed_at=order.created_at + timedelta(hours=12),
                bank_refund_id=f"BANK_RF_{order.bank_txn_id}",
                refunded_at=order.created_at + timedelta(hours=24),
            )
            refunds_created += 1

        # 再创建一笔待审核的退款
        pay_received_orders = [o for o in orders if o.status == "PAY_RECEIVED"]
        if pay_received_orders:
            order = pay_received_orders[0]
            RefundOrder.objects.create(
                refund_no=f"RF{order.order_no[3:]}",
                payment_order=order,
                refund_amount=order.amount,
                refund_reason="客户取消订单",
                status=RefundOrder.RefundStatus.PENDING_REVIEW,
            )
            refunds_created += 1

        self.stdout.write(f"    完成: {refunds_created} 笔退款")

    # ── 对账 ──────────────────────────────────────────────

    def _create_reconciliation(self, nostro_accounts):
        self.stdout.write("  创建对账数据...")

        # 昨天的对账批次 — 已完成
        batch1 = ReconciliationBatch.objects.create(
            batch_no="RECON20260707001",
            bank_code="CMB",
            bank_name="招商银行",
            reconciliation_date=_days_ago(1).date(),
            statement_file="/data/recon/CMB_20260707.csv",
            total_count_bank=8,
            total_amount_bank=Decimal("2356000.00"),
            total_count_platform=7,
            total_amount_platform=Decimal("2206000.00"),
            match_count=6,
            match_amount=Decimal("2206000.00"),
            diff_count=2,
            diff_amount=Decimal("150000.00"),
            status=ReconciliationBatch.BatchStatus.DIFF,
            started_at=_hours_ago(26),
            completed_at=_hours_ago(25),
        )
        ReconciliationDiff.objects.create(
            batch=batch1,
            diff_type=ReconciliationDiff.DiffType.BANK_ONLY,
            bank_txn_id="CMB20260707099",
            txn_time=_hours_ago(26),
            amount_bank=Decimal("100000.00"),
            amount_platform=None,
            resolution=ReconciliationDiff.ResolutionType.PENDING,
        )
        ReconciliationDiff.objects.create(
            batch=batch1,
            diff_type=ReconciliationDiff.DiffType.AMOUNT_DIFF,
            order_no="PAY20260700003",
            bank_txn_id="CMB20260627003",
            txn_time=_days_ago(8),
            amount_bank=Decimal("89000.00"),
            amount_platform=Decimal("88000.00"),
            resolution=ReconciliationDiff.ResolutionType.ADJUST_PLATFORM,
            resolution_note="平台金额有误，按银行金额调整",
            resolved_by="admin",
            resolved_at=_hours_ago(24),
        )

        # 前天的对账批次 — 已完成无差异
        ReconciliationBatch.objects.create(
            batch_no="RECON20260706001",
            bank_code="ICBC",
            bank_name="中国工商银行",
            reconciliation_date=_days_ago(2).date(),
            statement_file="/data/recon/ICBC_20260706.csv",
            total_count_bank=5,
            total_amount_bank=Decimal("1030000.00"),
            total_count_platform=5,
            total_amount_platform=Decimal("1030000.00"),
            match_count=5,
            match_amount=Decimal("1030000.00"),
            diff_count=0,
            diff_amount=Decimal("0"),
            status=ReconciliationBatch.BatchStatus.MATCHED,
            started_at=_hours_ago(50),
            completed_at=_hours_ago(49),
        )

        # Nostro 余额核对
        for acc in nostro_accounts[:2]:
            platform_bal = acc.balance
            bank_bal = platform_bal + random.choice([Decimal("0"), Decimal("-2000"), Decimal("5000")])
            NostroBalanceCheck.objects.create(
                check_date=_days_ago(1).date(),
                nostro_account=acc,
                platform_balance=platform_bal,
                bank_statement_balance=bank_bal,
                difference=bank_bal - platform_bal,
                is_balanced=(bank_bal == platform_bal),
                remark="自动核对" if bank_bal == platform_bal else "存在小额差异，需关注",
            )

        self.stdout.write("    完成: 2 批对账 + 2 条差异 + 2 条余额核对")

    # ── 清算 ──────────────────────────────────────────────

    def _create_settlement(self, merchants, orders):
        self.stdout.write("  创建清算数据...")

        # 每个有已收款订单的商户创建清算批次
        settled_orders_m1 = [o for o in orders if o.merchant == merchants[0] and o.status == "SETTLED"]
        settled_orders_m2 = [o for o in orders if o.merchant == merchants[1] and o.status == "SETTLED"]

        for merchant, settled_orders in [(merchants[0], settled_orders_m1), (merchants[1], settled_orders_m2)]:
            if not settled_orders:
                continue

            total_amount = sum(o.amount for o in settled_orders)
            total_fee = sum(o.fee_amount for o in settled_orders)
            net = total_amount - total_fee
            settle_date = _days_ago(1).date()

            batch = SettlementBatch.objects.create(
                batch_no=f"STL{settle_date.strftime('%Y%m%d')}{merchant.merchant_no[-3:]}",
                settle_date=settle_date,
                merchant=merchant,
                total_count=len(settled_orders),
                total_amount=total_amount,
                fee_total=total_fee,
                settle_net_amount=net,
                status=SettlementBatch.SettleStatus.SETTLED,
                settled_at=_hours_ago(12),
                settlement_account_info={
                    "bank_name": merchant.settlement_accounts.first().bank_name,
                    "account_name": merchant.settlement_accounts.first().account_name,
                },
            )

            for order in settled_orders:
                detail = SettlementDetail.objects.create(
                    batch=batch,
                    payment_order=order,
                    order_no=order.order_no,
                    amount=order.amount,
                    fee=order.fee_amount,
                    settle_amount=order.settle_amount,
                )
                # 手续费分润 (平台拿 60%, 渠道拿 40%)
                FeeShare.objects.create(
                    settlement_detail=detail,
                    channel_fee=(order.fee_amount * Decimal("0.4")).quantize(Decimal("0.0001")),
                    platform_fee=(order.fee_amount * Decimal("0.6")).quantize(Decimal("0.0001")),
                    agent_fee=Decimal("0"),
                )

        # 差异代销账
        DifferenceWriteOff.objects.create(
            write_off_no="WOF20260707001",
            merchant=merchants[0],
            amount=Decimal("1000.00"),
            reason="对账差异金额，经审批后销账",
            status=DifferenceWriteOff.WriteOffStatus.APPROVED,
            applied_by="admin",
            approved_by="admin",
            approved_at=_hours_ago(6),
        )

        self.stdout.write("    完成: 2 批清算 + 明细 + 分润 + 1 条代销账")

    # ── RBAC 种子数据 ─────────────────────────────────────

    def _create_rbac_data(self):
        self.stdout.write("  创建 RBAC 角色权限...")
        from apps.rbac.models import SystemUser, Role, Permission, UserRole, RolePermission
        from apps.rbac.services import AuthService

        auth_service = AuthService()

        permissions = [
            ("merchant:view", "查看商户", "merchant", "view"),
            ("merchant:create", "创建商户", "merchant", "create"),
            ("merchant:edit", "编辑商户", "merchant", "edit"),
            ("merchant:delete", "删除商户", "merchant", "delete"),
            ("merchant:approve", "审核商户", "merchant", "approve"),
            ("payment:view", "查看支付", "payment", "view"),
            ("payment:create", "创建支付", "payment", "create"),
            ("payment:refund", "发起退款", "payment", "refund"),
            ("payment:close", "关闭订单", "payment", "close"),
            ("refund:view", "查看退款", "refund", "view"),
            ("refund:approve", "审核退款", "refund", "approve"),
            ("account:view", "查看账户", "account", "view"),
            ("account:transfer", "资金调拨", "account", "transfer"),
            ("reconciliation:view", "查看对账", "reconciliation", "view"),
            ("reconciliation:manage", "处理差异", "reconciliation", "manage"),
            ("settlement:view", "查看清算", "settlement", "view"),
            ("settlement:manage", "管理清算", "settlement", "manage"),
            ("settlement:approve", "审批代销账", "settlement", "approve"),
            ("report:view", "查看报表", "report", "view"),
            ("report:export", "导出报表", "report", "export"),
            ("report:dashboard", "查看仪表盘", "report", "view"),
            ("system:view", "查看系统配置", "system", "view"),
            ("system:manage", "管理系统配置", "system", "manage"),
            ("system:user", "管理用户", "system", "user"),
            ("system:role", "管理角色", "system", "role"),
            ("system:audit", "查看审计日志", "system", "view"),
        ]

        perm_objs = {}
        for code, name, resource, action in permissions:
            perm_objs[code] = Permission.objects.create(
                code=code, name=name, resource=resource, action=action,
            )

        roles = {
            "super_admin": Role.objects.create(
                name="超级管理员", code="super_admin",
                description="系统最高权限，拥有所有功能和数据访问权限",
                is_system=True,
            ),
            "operator": Role.objects.create(
                name="操作员", code="operator",
                description="执行日常操作：商户管理、订单创建、退款发起、数据查看（不含审批权限）",
                is_system=True,
            ),
            "reviewer": Role.objects.create(
                name="复核", code="reviewer",
                description="复核操作质量：对账差异处理、审核数据一致性、审计日志查看",
                is_system=True,
            ),
            "approver": Role.objects.create(
                name="批复", code="approver",
                description="最终审批：商户审核、退款审批、清算审批",
                is_system=True,
            ),
            "finance": Role.objects.create(
                name="财务人员", code="finance",
                description="财务管理：对账、清算、报表、资金调拨",
                is_system=True,
            ),
            "auditor": Role.objects.create(
                name="审计人员", code="auditor",
                description="只读权限：查看所有数据、操作日志、导出报表",
                is_system=True,
            ),
            "merchant_admin": Role.objects.create(
                name="商户管理员", code="merchant_admin",
                description="管理自身商户，查看支付订单和清算数据",
                is_system=True,
            ),
        }

        role_perms = {
            "super_admin": list(perm_objs.keys()),
            # 操作员 — 执行操作，不能审批
            "operator": [
                "merchant:view", "merchant:create", "merchant:edit",
                "payment:view", "payment:create", "payment:refund", "payment:close",
                "refund:view",
                "reconciliation:view", "settlement:view",
                "report:view", "report:dashboard",
            ],
            # 复核 — 审查数据、处理差异
            "reviewer": [
                "merchant:view",
                "payment:view",
                "refund:view",
                "reconciliation:view", "reconciliation:manage",
                "settlement:view",
                "report:view", "report:export", "report:dashboard",
                "account:view",
                "system:audit",
            ],
            # 批复 — 最终审批
            "approver": [
                "merchant:view", "merchant:approve",
                "payment:view",
                "refund:view", "refund:approve",
                "reconciliation:view",
                "settlement:view", "settlement:approve",
                "report:view", "report:dashboard",
                "account:view",
            ],
            "finance": [
                "account:view", "account:transfer",
                "reconciliation:view", "reconciliation:manage",
                "settlement:view", "settlement:manage", "settlement:approve",
                "report:view", "report:export", "report:dashboard",
                "merchant:view", "payment:view", "refund:view",
            ],
            "auditor": [
                "merchant:view", "payment:view", "refund:view",
                "account:view", "reconciliation:view", "settlement:view",
                "report:view", "report:export", "report:dashboard",
                "system:view", "system:audit",
            ],
            "merchant_admin": [
                "merchant:view",
                "payment:view", "refund:view",
                "reconciliation:view", "settlement:view",
                "report:view", "report:dashboard",
            ],
        }

        for role_code, perm_codes in role_perms.items():
            role = roles[role_code]
            for code in perm_codes:
                RolePermission.objects.create(role=role, permission=perm_objs[code])

        users = [
            ("admin", "Admin@123", "系统管理员", "13800000001", "admin@b2bpay.com", ["super_admin"]),
            ("operator_zhang", "Op@123456", "张操作", "13800000002", "op_zhang@b2bpay.com", ["operator"]),
            ("reviewer_li", "Rev@123456", "李复核", "13800000004", "rev_li@b2bpay.com", ["reviewer"]),
            ("approver_zhao", "Apr@123456", "赵批复", "13800000005", "apr_zhao@b2bpay.com", ["approver"]),
            ("finance_wang", "Fin@123456", "王财务", "13800000003", "fin_wang@b2bpay.com", ["finance"]),
        ]

        for username, password, real_name, phone, email, role_codes in users:
            auth_service.create_user(
                username=username, password=password,
                real_name=real_name, phone=phone, email=email,
                role_codes=role_codes,
            )

        self.stdout.write(f"    完成: {len(permissions)} 权限 + {len(roles)} 角色 + {len(users)} 运营账号")

    # ── 用户端种子数据 ────────────────────────────────────

    def _create_user_portal_data(self, merchants, orders):
        self.stdout.write("  创建用户端数据...")
        from apps.user_portal.models import EndUser
        from apps.account.models import UserAccount, UserPaymentDetail

        m1, m2 = merchants[0], merchants[1]

        test_users = [
            ("13912345001", "User@123", "刘老板", "刘建国"),
            ("13912345002", "User@123", "陈经理", "陈文博"),
            ("13912345003", "User@123", "赵会计", "赵丽萍"),
            ("13912345004", "User@123", "孙代理", ""),
            ("13912345005", "User@123", "周先生", ""),
            ("13912345006", "User@123", "吴总", "吴海龙"),
        ]

        end_users = []
        for phone, password, nickname, real_name in test_users:
            pwd_hash = hashlib.sha256(f"user:{password}:b2b_user_salt".encode()).hexdigest()
            user = EndUser.objects.create(
                phone=phone,
                password_hash=pwd_hash,
                nickname=nickname,
                real_name=real_name,
                is_verified=bool(real_name),
            )
            end_users.append(user)

        UserAccount.objects.create(
            user_id=str(end_users[0].id),
            merchant=m1,
            bank_code="CMB",
            bank_name="招商银行",
            account_holder="刘建国",
            account_number=encrypt_field("6225880150001234"),
            bind_token=encrypt_field("token_liu_001"),
            status=UserAccount.BindStatus.ACTIVE,
            bind_at=_days_ago(30),
        )
        UserAccount.objects.create(
            user_id=str(end_users[0].id),
            merchant=m1,
            bank_code="ICBC",
            bank_name="中国工商银行",
            account_holder="刘建国",
            account_number=encrypt_field("6222020123456789"),
            bind_token=encrypt_field("token_liu_002"),
            status=UserAccount.BindStatus.ACTIVE,
            bind_at=_days_ago(20),
        )
        UserAccount.objects.create(
            user_id=str(end_users[1].id),
            merchant=m2,
            bank_code="CMB",
            bank_name="招商银行",
            account_holder="陈文博",
            account_number=encrypt_field("6225880160005678"),
            bind_token=encrypt_field("token_chen_001"),
            status=UserAccount.BindStatus.ACTIVE,
            bind_at=_days_ago(15),
        )

        pay_methods = ["WIRE_TRANSFER", "ONLINE_BANK", "AUTHORIZED"]
        payment_detail_count = 0
        for i, order in enumerate(orders):
            if order.status in ("PRE_CREATE", "PENDING_PAY", "CLOSED"):
                continue
            user = end_users[i % len(end_users)]
            UserPaymentDetail.objects.create(
                user_id=str(user.id),
                order=order,
                account=None,
                pay_method=order.pay_method or random.choice(pay_methods),
                amount=order.amount,
                pay_time=order.pay_received_at or order.created_at,
            )
            # 更新订单的 user_id
            if order.user_id == "" or order.user_id is None:
                pass
            payment_detail_count += 1

        self.stdout.write(f"    完成: {len(end_users)} 终端用户 + 3 绑定账户 + {payment_detail_count} 支付明细")
