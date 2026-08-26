"""对账 — 定时任务（同步）。"""
from datetime import date, timedelta
import logging

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
            _reconcile_bank(bank_code, recon_date)
        except Exception as e:
            logger.error(f"对账失败 [{bank_code}]: {e}")


def _reconcile_bank(bank_code: str, recon_date: date):
    """对单个银行执行对账。"""
    fetcher = BankFileFetcher()
    matcher = ReconciliationMatcher()

    batch = ReconciliationBatch.objects.create(
        batch_no=generate_reconciliation_batch_no(),
        bank_code=bank_code,
        reconciliation_date=recon_date,
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

    logger.info(
        f"对账完成 [{bank_code}] {recon_date}: "
        f"bank={len(bank_lines)}, platform={len(platform_orders)}, "
        f"matched={len(result.matched)}, diffs={len(diffs_to_create)}"
    )


def check_nostro_balance():
    """核对所有 Nostro 账户余额。"""
    checker = FundChecker()
    accounts = NostroAccount.objects.filter(is_active=True, is_deleted=False)

    for account in accounts:
        try:
            bank_balance = account.balance
            checker.check_nostro_balance(account, bank_balance)
        except Exception as e:
            logger.error(f"Nostro 余额核对失败 [{account.account_no}]: {e}")
