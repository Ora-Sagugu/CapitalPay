"""对账 — 定时任务（同步）。"""
from datetime import date, timedelta
import logging

from django.db.models import Sum
from django.utils import timezone

from apps.reconciliation.models import ReconciliationBatch, ReconciliationDiff
from apps.reconciliation.engine import BankFileFetcher, ReconciliationMatcher, FundChecker, ConfirmationHandler
from apps.account.models import NostroAccount
from apps.core.utils import generate_reconciliation_batch_no

logger = logging.getLogger(__name__)


def run_daily_reconciliation():
    """日终对账。

    流程:
        1. 获取各家银行对账文件
        2. 提取平台当日交易
        3. 双向匹配
        4. 生成差异记录
        5. 资金核对
    """
    from apps.payment.gateway import BankGatewayRouter

    recon_date = (timezone.now() - timedelta(days=1)).date()

    for bank_info in BankGatewayRouter.list_banks():
        bank_code = bank_info["bank_code"]
        try:
            _reconcile_bank(bank_code, recon_date, bank_info.get("bank_name") or "")
        except Exception as e:
            logger.error(f"对账失败 [{bank_code}]: {e}")


def _reconcile_bank(bank_code: str, recon_date: date, bank_name: str = ""):
    """对单个银行执行对账。"""
    fetcher = BankFileFetcher()
    matcher = ReconciliationMatcher()

    batch = ReconciliationBatch.objects.create(
        batch_no=generate_reconciliation_batch_no(),
        bank_code=bank_code,
        bank_name=bank_name or bank_code,
        reconciliation_date=recon_date,
        recon_type="TRANSACTION",
        status=ReconciliationBatch.BatchStatus.FETCHING,
        started_at=timezone.now(),
    )

    try:
        filepath = fetcher.fetch_daily_statement(bank_code, recon_date)
        batch.statement_file = filepath
        batch.status = ReconciliationBatch.BatchStatus.MATCHING
        batch.save()
    except Exception as e:
        batch.status = ReconciliationBatch.BatchStatus.DIFF
        batch.save()
        raise

    bank_lines = matcher.parse_bank_csv(filepath)
    platform_orders = matcher.get_platform_orders(recon_date)

    batch.total_count_bank = len(bank_lines)
    batch.total_amount_bank = sum(l.amount for l in bank_lines)
    batch.total_count_platform = len(platform_orders)
    batch.total_amount_platform = sum(o.amount for o in platform_orders)
    batch.save()

    result = matcher.match(bank_lines, platform_orders)

    batch.match_count = len(result.matched)
    batch.match_amount = sum(m["bank"].amount for m in result.matched)
    batch.diff_count = len(result.bank_only) + len(result.platform_only) + len(result.amount_diff)

    if batch.diff_count > 0:
        batch.status = ReconciliationBatch.BatchStatus.DIFF
    else:
        batch.status = ReconciliationBatch.BatchStatus.MATCHED

    batch.completed_at = timezone.now()
    batch.save()

    confirmation_handler = ConfirmationHandler()
    confirm_result = confirmation_handler.process_matches(result, batch)
    logger.info(
        f"PRN auto-confirm [{bank_code}]: confirmed={confirm_result['auto_confirmed']}, "
        f"fee_credited={confirm_result['fee_credited']}, skipped={confirm_result['skipped']}"
    )

    diffs_to_create = []

    for bank_line in result.bank_only:
        diffs_to_create.append(ReconciliationDiff(
            batch=batch,
            diff_type=ReconciliationDiff.DiffType.BANK_ONLY,
            bank_txn_id=bank_line.txn_id,
            txn_time=bank_line.txn_time,
            amount_bank=bank_line.amount,
        ))

    for platform_order in result.platform_only:
        diffs_to_create.append(ReconciliationDiff(
            batch=batch,
            diff_type=ReconciliationDiff.DiffType.PLATFORM_ONLY,
            order_no=platform_order.order_no,
            amount_platform=platform_order.amount,
        ))

    for item in result.amount_diff:
        diff_type = item.get("diff_type", ReconciliationDiff.DiffType.AMOUNT_DIFF)
        prn_code = item.get("prn_code")
        diffs_to_create.append(ReconciliationDiff(
            batch=batch,
            diff_type=ReconciliationDiff.DiffType.AMOUNT_DIFF
            if diff_type != "PRN_MISMATCH" else ReconciliationDiff.DiffType.AMOUNT_DIFF,
            order_no=item["platform"].order_no,
            prn_code=prn_code,
            bank_txn_id=item["bank"].txn_id,
            txn_time=item["bank"].txn_time,
            amount_bank=item["bank"].amount,
            amount_platform=item["platform"].amount,
        ))

    if diffs_to_create:
        ReconciliationDiff.objects.bulk_create(diffs_to_create)
        from apps.reconciliation.alerts import fire_recon_alerts
        fire_recon_alerts(batch, len(diffs_to_create))

    logger.info(
        f"对账完成 [{bank_code}] {recon_date}: "
        f"bank={len(bank_lines)}, platform={len(platform_orders)}, "
        f"matched={len(result.matched)}, diffs={len(diffs_to_create)}"
    )


def check_nostro_balance():
    """核对所有 Nostro 账户余额。"""
    from decimal import Decimal
    from apps.payment.models import PaymentOrder

    checker = FundChecker()
    accounts = NostroAccount.objects.filter(is_active=True, is_deleted=False)

    for account in accounts:
        try:
            pending = PaymentOrder.objects.filter(
                is_deleted=False,
                bank_code=account.bank_code,
                status="PENDING_PAY",
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
            bank_balance = (account.balance or Decimal("0")) + pending
            checker.check_nostro_balance(account, bank_balance)
        except Exception as e:
            logger.error(f"Nostro 余额核对失败 [{account.account_no}]: {e}")


def run_settlement_fund_reconciliation(recon_date: date = None):
    """银行汇款资金清算核对 — 结算批次 vs Mock 清算文件。"""
    from decimal import Decimal
    from apps.settlement.models import SettlementBatch
    from apps.core.utils import generate_reconciliation_batch_no

    recon_date = recon_date or (timezone.now() - timedelta(days=1)).date()
    batches = list(SettlementBatch.objects.filter(settle_date=recon_date, is_deleted=False))
    bank_code = "MOCK"
    bank_name = "模拟银行"
    recon = ReconciliationBatch.objects.create(
        batch_no=generate_reconciliation_batch_no(),
        bank_code=bank_code,
        bank_name=bank_name,
        reconciliation_date=recon_date,
        recon_type="SETTLEMENT_FUND",
        status=ReconciliationBatch.BatchStatus.MATCHING,
        started_at=timezone.now(),
        total_count_platform=len(batches),
        total_amount_platform=sum((b.settle_net_amount or 0) for b in batches),
        total_count_bank=len(batches),
        total_amount_bank=sum((b.settle_net_amount or 0) for b in batches),
    )
    diffs = []
    matched = 0
    for b in batches:
        bank_amount = b.settle_net_amount
        if b.status != SettlementBatch.SettleStatus.SETTLED:
            diffs.append(ReconciliationDiff(
                batch=recon,
                diff_type=ReconciliationDiff.DiffType.STATUS_DIFF,
                order_no=b.batch_no,
                amount_platform=b.settle_net_amount,
                amount_bank=bank_amount,
            ))
        else:
            matched += 1
    recon.match_count = matched
    recon.diff_count = len(diffs)
    recon.status = (
        ReconciliationBatch.BatchStatus.DIFF if diffs else ReconciliationBatch.BatchStatus.MATCHED
    )
    recon.completed_at = timezone.now()
    recon.save()
    if diffs:
        ReconciliationDiff.objects.bulk_create(diffs)
    logger.info("settlement fund recon %s matched=%s diffs=%s", recon_date, matched, len(diffs))
    return recon
