"""汇款申请事务服务：报价绑定、幂等、额度预留与订单创建。"""
import hashlib
import json
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.exceptions import BusinessException, ErrorCode
from apps.core.utils import generate_uin
from apps.merchant.models import Merchant
from apps.payment.models import (
    AgentDailyRemittanceUsage,
    MerchantDailyRemittanceUsage,
    PaymentOrder,
    RemittanceQuote,
)
from apps.settlement.engine.calculator import SettlementCalculator

from .remittance_policy import RemittanceEligibilityPolicy


def agent_payout_gate_required(order) -> bool:
    """Merchant remittances no longer wait for an agent payout request."""
    return False


def arm_agent_payout_request(order: PaymentOrder) -> PaymentOrder:
    """Mark a collected bound-agent order as awaiting Agent Request payout."""
    if not agent_payout_gate_required(order):
        return order
    if order.agent_payout_request_status == PaymentOrder.AgentPayoutRequestStatus.REQUESTED:
        return order
    order.agent_payout_request_status = PaymentOrder.AgentPayoutRequestStatus.PENDING
    return order


def assert_confirm_transfer_allowed(order: PaymentOrder) -> None:
    if not agent_payout_gate_required(order):
        return
    if order.status != PaymentOrder.OrderStatus.PAY_RECEIVED:
        raise BusinessException(
            ErrorCode.AGENT_PAYOUT_REQUEST_REQUIRED,
            "Bound-agent instructions must be collected first, then the agent must request payout before Confirm transfer",
            409,
        )
    if order.agent_payout_request_status != PaymentOrder.AgentPayoutRequestStatus.REQUESTED:
        raise BusinessException(
            ErrorCode.AGENT_PAYOUT_REQUEST_REQUIRED,
            "The agent must request payout before operations can confirm transfer",
            409,
        )


def awaiting_confirm_transfer_q() -> Q:
    """Orders that currently show Confirm transfer on Remittance Orders."""
    pending = PaymentOrder.AgentPayoutRequestStatus.PENDING
    requested = PaymentOrder.AgentPayoutRequestStatus.REQUESTED
    return (
        Q(status=PaymentOrder.OrderStatus.PAY_RECEIVED)
        & ~Q(agent_payout_request_status=pending)
    ) | (
        Q(status=PaymentOrder.OrderStatus.PENDING_PAY)
        & ~Q(agent_payout_request_status__in=[pending, requested])
    )


def filter_awaiting_confirm_transfer(qs):
    return qs.filter(awaiting_confirm_transfer_q())


def request_payload_hash(payload: dict, *, merchant_no: str, user_id: str) -> str:
    canonical = {
        "merchant": merchant_no,
        "user_id": user_id or "",
        **{key: payload.get(key, "") for key in sorted(payload)},
    }
    raw = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class RemittanceApplicationService:
    @staticmethod
    def initial_review_state(merchant: Merchant, actor_type: str) -> tuple[str, str]:
        """Merchant and agent submissions both go straight to operations review."""
        return (
            PaymentOrder.OrderStatus.PENDING_REVIEW,
            PaymentOrder.AgentReviewStatus.NONE,
        )

    @transaction.atomic
    def submit(
        self,
        *,
        merchant: Merchant | None = None,
        agent=None,
        agent_customer=None,
        payload: dict,
        idempotency_key: str,
        user_id: str = "",
        actor_type: str,
        order_user_id: str | None = None,
    ) -> tuple[PaymentOrder, bool]:
        idempotency_key = (idempotency_key or "").strip()
        if not idempotency_key:
            raise BusinessException(
                "IDEMPOTENCY_KEY_REQUIRED",
                "The Idempotency-Key header is required; please refresh and retry",
                400,
            )
        if len(idempotency_key) > 64:
            raise BusinessException("IDEMPOTENCY_KEY_INVALID", "The Idempotency-Key exceeds the permitted length", 400)

        book_no = merchant.merchant_no if merchant is not None else (agent.agent_no if agent is not None else "")
        digest = request_payload_hash(
            payload,
            merchant_no=book_no,
            user_id=user_id,
        )
        existing = PaymentOrder.objects.select_for_update().filter(
            idempotency_key=idempotency_key
        ).first()
        if existing:
            if existing.request_payload_hash == digest:
                return existing, False
            raise BusinessException(
                "IDEMPOTENCY_CONFLICT",
                "This idempotency key has already been used for a different remittance application",
                409,
            )

        quote_no = payload["quote_id"]
        quote_qs = RemittanceQuote.objects.select_for_update().filter(
            quote_no=quote_no,
            is_deleted=False,
        )
        if merchant is not None:
            quote_qs = quote_qs.filter(merchant_id=merchant.id)
        elif agent is not None:
            quote_qs = quote_qs.filter(agent_id=agent.id)
        quote = quote_qs.first()
        if not quote:
            raise BusinessException("QUOTE_NOT_FOUND", "The quotation does not exist; please obtain a new quotation", 404)
        if agent_customer is None and quote.agent_customer_id:
            agent_customer = quote.agent_customer
        elif (
            agent_customer is not None
            and quote.agent_customer_id
            and quote.agent_customer_id != agent_customer.id
        ):
            raise BusinessException(
                "CUSTOMER_MISMATCH",
                "The selected customer does not match this quotation",
                409,
            )
        if quote.actor_type != actor_type:
            raise BusinessException("QUOTE_OWNER_MISMATCH", "The quotation originator does not match the authenticated principal", 403)
        if actor_type in ("CUSTOMER", "AGENT") and quote.user_id != str(user_id):
            raise BusinessException("QUOTE_OWNER_MISMATCH", "The authenticated principal is not authorised to use this quotation", 403)
        if quote.status != RemittanceQuote.QuoteStatus.ACTIVE:
            retry_order = PaymentOrder.objects.filter(
                idempotency_key=idempotency_key,
                request_payload_hash=digest,
            ).first()
            if retry_order:
                return retry_order, False
            raise BusinessException("QUOTE_ALREADY_USED", "This quotation has already been consumed; please obtain a new quotation", 409)
        if quote.expires_at <= timezone.now():
            raise BusinessException("QUOTE_EXPIRED", "The quotation has expired; please obtain a new quotation", 422)

        if agent is not None:
            from apps.agent.models import Agent
            from apps.payment.services.remittance_policy import AgentRemittanceEligibilityPolicy

            agent = Agent.objects.select_for_update().get(pk=agent.pk)
            usage, created = AgentDailyRemittanceUsage.objects.get_or_create(
                agent=agent,
                usage_date=timezone.localdate(),
                defaults={"total_amount": Decimal("0"), "order_count": 0},
            )
            if not created:
                usage = AgentDailyRemittanceUsage.objects.select_for_update().get(pk=usage.pk)
            AgentRemittanceEligibilityPolicy().assert_eligible(agent, agent_customer, quote.amount)
        else:
            if merchant is None:
                raise BusinessException("MERCHANT_REQUIRED", "A merchant is required for this remittance", 400)
            merchant = Merchant.objects.select_for_update().select_related("agent").get(pk=merchant.pk)
            usage, created = MerchantDailyRemittanceUsage.objects.get_or_create(
                merchant=merchant,
                usage_date=timezone.localdate(),
                defaults={"total_amount": Decimal("0"), "order_count": 0},
            )
            if not created:
                usage = MerchantDailyRemittanceUsage.objects.select_for_update().get(pk=usage.pk)
            RemittanceEligibilityPolicy().assert_eligible(
                merchant,
                quote.amount,
                customer=agent_customer,
                require_customer=(actor_type == "CUSTOMER"),
            )

        from apps.compliance.services import scan_entity_lightweight
        scan = scan_entity_lightweight(
            payload["beneficiary_name"],
            payload.get("beneficiary_address", ""),
        )
        for hit in scan.get("name_hits", []):
            if (
                hit.get("risk_level") == "HIGH"
                and hit.get("match_type") in ("exact_name", "alias_name")
            ):
                raise BusinessException(
                    "SANCTION_BLOCKED",
                    "The beneficiary name matches a high-risk sanctions list; the application has been blocked",
                    422,
                )

        now = timezone.now()
        initial_status, agent_review_status = self.initial_review_state(merchant, actor_type)
        owner_user_id = order_user_id if order_user_id is not None else user_id
        prefix = "A" if agent is not None else "M"
        order = PaymentOrder.objects.create(
            order_no=f"RMT{now:%Y%m%d%H%M%S}{uuid.uuid4().hex[:6].upper()}",
            merchant_order_no=f"{prefix}{now:%Y%m%d%H%M%S}{uuid.uuid4().hex[:4].upper()}",
            unique_identification_no=generate_uin(),
            idempotency_key=idempotency_key,
            request_payload_hash=digest,
            quote=quote,
            merchant=merchant,
            agent=agent,
            agent_customer=agent_customer,
            user_id=str(owner_user_id) if owner_user_id else None,
            amount=quote.amount,
            currency=quote.to_currency,
            from_currency=quote.from_currency,
            to_currency=quote.to_currency,
            fee_bearing=quote.fee_bearing,
            fee_amount=quote.fee_amount,
            fee_currency=quote.fee_currency,
            sender_total_amount=quote.sender_total_amount,
            settle_amount=quote.settle_amount,
            exchange_rate=quote.exchange_rate,
            rate_source=quote.rate_source,
            applied_fee_model=quote.fee_model,
            applied_fee_rate=quote.fee_rate,
            applied_fixed_fee=quote.fixed_fee,
            beneficiary_name=payload["beneficiary_name"],
            beneficiary_bank=payload["beneficiary_bank"],
            beneficiary_account=payload["beneficiary_account"],
            beneficiary_swift=payload.get("beneficiary_swift", ""),
            beneficiary_address=payload.get("beneficiary_address", ""),
            remittance_purpose=payload.get("remittance_purpose", ""),
            contract_file=payload.get("contract_file", ""),
            pay_method=payload.get("pay_method") or PaymentOrder.PayMethod.WIRE_TRANSFER,
            status=initial_status,
            agent_review_status=agent_review_status,
            expire_at=now + timedelta(days=7),
            status_history=[{
                "status": initial_status,
                "time": now.isoformat(),
                "quote_id": quote.quote_no,
                "agent_review_status": agent_review_status,
            }],
        )

        usage.total_amount += quote.amount
        usage.order_count += 1
        usage.save(update_fields=["total_amount", "order_count", "updated_at"])

        # FeeShare 是订单财务快照的一部分；失败时整笔事务回滚。
        SettlementCalculator().calculate_fee_share(order)

        quote.status = RemittanceQuote.QuoteStatus.USED
        quote.used_at = now
        quote.save(update_fields=["status", "used_at", "updated_at"])
        return order, True

    @transaction.atomic
    def release_reserved_usage(self, order: PaymentOrder) -> None:
        """驳回当日提交的申请时释放预留额度；重复调用保持幂等。"""
        if not order.quote_id:
            return
        usage_date = timezone.localtime(order.created_at).date()
        if order.agent_id:
            usage = AgentDailyRemittanceUsage.objects.select_for_update().filter(
                agent_id=order.agent_id,
                usage_date=usage_date,
                is_deleted=False,
            ).first()
        elif order.merchant_id:
            usage = MerchantDailyRemittanceUsage.objects.select_for_update().filter(
                merchant=order.merchant,
                usage_date=usage_date,
                is_deleted=False,
            ).first()
        else:
            return
        if not usage:
            return
        usage.total_amount = max(Decimal("0"), usage.total_amount - order.amount)
        usage.order_count = max(0, usage.order_count - 1)
        usage.save(update_fields=["total_amount", "order_count", "updated_at"])

    @transaction.atomic
    def review_by_agent(
        self,
        order: PaymentOrder,
        *,
        action: str,
        remark: str = "",
        reviewer: str = "",
    ) -> PaymentOrder:
        """Agent agree sends the order to ops; reject closes it and releases usage."""
        locked = PaymentOrder.objects.select_for_update().select_related("merchant").get(pk=order.pk)
        if locked.status != PaymentOrder.OrderStatus.PENDING_AGENT_REVIEW:
            raise BusinessException(
                "AGENT_ORDER_STATUS_INVALID",
                "This instruction is not awaiting agent review",
                409,
            )
        normalized = (action or "").strip().lower()
        if normalized in ("agree", "approve"):
            now = timezone.now()
            locked.status = PaymentOrder.OrderStatus.PENDING_REVIEW
            locked.agent_review_status = PaymentOrder.AgentReviewStatus.APPROVED
            locked.agent_reviewed_by = reviewer
            locked.agent_reviewed_at = now
            locked.agent_review_comment = remark or "Agreed"
            locked.add_status_history(PaymentOrder.OrderStatus.PENDING_REVIEW, {
                "actor": "AGENT",
                "action": "agree",
                "reviewed_by": reviewer,
            })
            locked.save(update_fields=[
                "status", "agent_review_status", "agent_reviewed_by",
                "agent_reviewed_at", "agent_review_comment",
                "status_history", "updated_at",
            ])
            return locked
        if normalized == "reject":
            reason = (remark or "").strip()
            if not reason:
                raise BusinessException(
                    "REJECT_REASON_REQUIRED",
                    "A rejection reason is required",
                    400,
                )
            now = timezone.now()
            locked.status = PaymentOrder.OrderStatus.CLOSED
            locked.agent_review_status = PaymentOrder.AgentReviewStatus.REJECTED
            locked.agent_reviewed_by = reviewer
            locked.agent_reviewed_at = now
            locked.agent_review_comment = reason
            locked.closed_at = now
            locked.add_status_history(PaymentOrder.OrderStatus.CLOSED, {
                "actor": "AGENT",
                "action": "reject",
                "reason": reason,
                "reviewed_by": reviewer,
            })
            locked.save(update_fields=[
                "status", "agent_review_status", "agent_reviewed_by",
                "agent_reviewed_at", "agent_review_comment",
                "closed_at", "status_history", "updated_at",
            ])
            self.release_reserved_usage(locked)
            return locked
        raise BusinessException("INVALID_ACTION", "The review action is invalid")

    @transaction.atomic
    def request_payout_by_agent(self, order: PaymentOrder, *, reviewer: str = "") -> PaymentOrder:
        """Agent urges ops to Confirm transfer after funds have been collected."""
        locked = PaymentOrder.objects.select_for_update().select_related("merchant").get(pk=order.pk)
        if not agent_payout_gate_required(locked):
            raise BusinessException(
                "AGENT_PAYOUT_REQUEST_NOT_REQUIRED",
                "This instruction does not require an agent payout request",
                409,
            )
        if locked.status != PaymentOrder.OrderStatus.PAY_RECEIVED:
            raise BusinessException(
                "AGENT_PAYOUT_STATUS_INVALID",
                "Payout can only be requested after funds have been received",
                409,
            )
        current = locked.agent_payout_request_status
        if current == PaymentOrder.AgentPayoutRequestStatus.REQUESTED:
            return locked
        if current not in (
            PaymentOrder.AgentPayoutRequestStatus.PENDING,
            PaymentOrder.AgentPayoutRequestStatus.NONE,
        ):
            raise BusinessException(
                "AGENT_PAYOUT_STATUS_INVALID",
                "This instruction is not awaiting an agent payout request",
                409,
            )
        now = timezone.now()
        locked.agent_payout_request_status = PaymentOrder.AgentPayoutRequestStatus.REQUESTED
        locked.agent_payout_requested_by = reviewer
        locked.agent_payout_requested_at = now
        locked.add_status_history("AGENT_PAYOUT_REQUESTED", {
            "actor": "AGENT",
            "requested_by": reviewer,
        })
        locked.save(update_fields=[
            "agent_payout_request_status", "agent_payout_requested_by",
            "agent_payout_requested_at", "status_history", "updated_at",
        ])
        return locked
