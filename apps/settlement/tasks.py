"""清结算 — 定时任务（同步）。"""
from datetime import timedelta
import logging

from django.utils import timezone

from .engine.batch_creator import SettlementBatchCreator
from .engine.calculator import SettlementCalculator
from .engine.distributor import FundsDistributor

logger = logging.getLogger(__name__)


def run_daily_settlement():
    """日终清算。

    流程:
        1. 按商户分组创建清算批次
        2. 计算手续费分润
        3. 执行资金划拨
    """
    settle_date = (timezone.now() - timedelta(days=1)).date()

    creator = SettlementBatchCreator()
    batches = creator.create_daily_batches(settle_date)
    logger.info(f"清算批次创建完成: {len(batches)} 批")

    calculator = SettlementCalculator()
    for batch in batches:
        try:
            calculator.calculate_batch_share(batch)
        except Exception as e:
            logger.error(f"分润计算失败 [{batch.batch_no}]: {e}")

    distributor = FundsDistributor()
    for batch in batches:
        try:
            batch = distributor.distribute(batch)
            logger.info(f"资金划拨完成: {batch.batch_no}")
        except Exception as e:
            logger.error(f"资金划拨失败 [{batch.batch_no}]: {e}")
