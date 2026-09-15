"""不可变资金流水写入服务。"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.utils import generate_batch_no
from .models import MoneyMovement


class MoneyMovementService:
    """幂等写入资金流水。已存在则原样返回，绝不更新。"""

    @transaction.atomic
    def record(
        self,
        *,
        movement_type: str,
        amount,
        currency: str,
        source_type: str,
        source_id: str,
        status: str = MoneyMovement.MovementStatus.SUCCESS,
        evidence_level: str = MoneyMovement.EvidenceLevel.SYSTEM_CONFIRMED,
        occurred_at=None,
        from_party_type: str = "",
        from_party_id: str = "",
        from_account: str = "",
        to_party_type: str = "",
        to_party_id: str = "",
        to_account: str = "",
        bank_code: str = "",
        bank_txn_id: str = "",
        payment_order=None,
        settlement_batch=None,
        refund_order=None,
        remark: str = "",
        extra: dict | None = None,
    ) -> MoneyMovement:
        existing = MoneyMovement.objects.filter(
            source_type=source_type,
            source_id=str(source_id),
            movement_type=movement_type,
        ).first()
        if existing:
            return existing

        return MoneyMovement.objects.create(
            movement_no=generate_batch_no("MV"),
            occurred_at=occurred_at or timezone.now(),
            movement_type=movement_type,
            status=status,
            evidence_level=evidence_level,
            amount=Decimal(str(amount)),
            currency=(currency or "")[:3],
            from_party_type=from_party_type,
            from_party_id=str(from_party_id or ""),
            from_account=from_account or "",
            to_party_type=to_party_type,
            to_party_id=str(to_party_id or ""),
            to_account=to_account or "",
            bank_code=bank_code or "",
            bank_txn_id=bank_txn_id or "",
            source_type=source_type,
            source_id=str(source_id),
            payment_order=payment_order,
            settlement_batch=settlement_batch,
            refund_order=refund_order,
            remark=remark or "",
            extra=extra or {},
        )
