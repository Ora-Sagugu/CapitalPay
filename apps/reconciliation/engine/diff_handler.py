"""对账引擎 — 差错处理。"""
import logging
from decimal import Decimal

from django.utils import timezone
from apps.reconciliation.models import ReconciliationDiff

logger = logging.getLogger(__name__)


class DiffHandler:
    """对账差异处理服务。"""

    def resolve_diff(
        self,
        diff: ReconciliationDiff,
        resolution: str,
        resolved_by: str,
        note: str = "",
    ) -> ReconciliationDiff:
        """处理单个差异记录。"""
        if diff.resolution != ReconciliationDiff.ResolutionType.PENDING:
            from apps.core.exceptions import BusinessException
            raise BusinessException("DIFF_ALREADY_RESOLVED", "This discrepancy has already been resolved")

        # 先执行侧效，成功后再落库 resolution，避免银行失败仍标记已处理
        if resolution == ReconciliationDiff.ResolutionType.ADJUST_PLATFORM:
            self._adjust_platform(diff, note)
        elif resolution == ReconciliationDiff.ResolutionType.ADJUST_BANK:
            self._request_bank_adjustment(diff, note)

        diff.resolution = resolution
        diff.resolved_by = resolved_by
        diff.resolved_at = timezone.now()
        diff.resolution_note = note
        diff.save(update_fields=["resolution", "resolved_by", "resolved_at", "resolution_note"])

        self._check_batch_complete(diff.batch)
        return diff

    def _adjust_platform(self, diff: ReconciliationDiff, note: str):
        """以平台为准 — 创建调账申请进入审批。"""
        logger.info("recon.adjust_platform diff_id=%s", diff.pk)
        try:
            from apps.adjustment.services import AdjustmentService
            from apps.adjustment.models import AdjustmentApplication
            AdjustmentService.create_application({
                "diff_type": AdjustmentApplication.DiffType.AMOUNT,
                "order_no": getattr(diff, "order_no", "") or "",
                "bank_channel": getattr(diff.batch, "bank_code", "") or "",
                "amount": diff.amount_platform or diff.amount_bank or Decimal("0"),
                "currency": "CNY",
                "reason": note or f"对账差异自动调账 {diff.pk}",
                "adjustment_amount": (diff.amount_platform or Decimal("0")) - (diff.amount_bank or Decimal("0")),
                "applicant": "recon-system",
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("recon.adjust_platform failed: %s", exc)
            raise

    def _request_bank_adjustment(self, diff: ReconciliationDiff, note: str):
        """以银行为准 — 向银行发起调账。"""
        from apps.payment.gateway import BankGatewayRouter
        from apps.core.exceptions import BusinessException

        bank_code = getattr(diff.batch, "bank_code", None)
        gateway = BankGatewayRouter.get_gateway(bank_code)
        amount = diff.amount_bank or diff.amount_platform or Decimal("0")
        logger.info("recon.adjust_bank diff_id=%s bank=%s", diff.pk, bank_code)
        try:
            result = gateway.request_adjustment(
                bank_txn_id=getattr(diff, "bank_txn_id", "") or "",
                amount=amount,
                reason=note,
                diff_id=str(diff.pk),
            )
        except NotImplementedError as exc:
            raise BusinessException("BANK_ADJUST_NOT_CONFIGURED", str(exc))
        if not result.get("success"):
            raise BusinessException("BANK_ADJUST_FAILED", result.get("message", ""))

    def _check_batch_complete(self, batch):
        """检查批次是否所有差异已处理。"""
        pending = batch.diffs.filter(
            resolution=ReconciliationDiff.ResolutionType.PENDING
        ).count()

        if pending == 0:
            batch.status = batch.BatchStatus.RESOLVED
            batch.save(update_fields=["status"])
