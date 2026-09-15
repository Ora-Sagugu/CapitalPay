"""审计商户、KYC、汇款产品和用户初审状态的一致性。"""
import json

from django.core.management.base import BaseCommand

from apps.merchant.models import Merchant
from apps.merchant.services import MerchantLifecycleService
from apps.payment.services.remittance_policy import RemittanceEligibilityPolicy
from apps.user_portal.models import EndUser


class Command(BaseCommand):
    help = "审计商户生命周期一致性；--fix 仅暂停不合格 ACTIVE 商户，不会自动激活待审商户"

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true", help="安全修复：暂停不合格 ACTIVE 商户")
        parser.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")

    def handle(self, *args, **options):
        issues = []
        policy = RemittanceEligibilityPolicy()

        approved_pending = EndUser.objects.filter(
            onboarding_status="approved",
            default_merchant__status=Merchant.Status.PENDING,
            is_deleted=False,
        ).select_related("default_merchant")
        for user in approved_pending:
            issues.append({
                "severity": "INFO",
                "code": "KYC_PENDING",
                "merchant_no": user.default_merchant.merchant_no,
                "user_id": str(user.id),
                "message": "资料初审已通过，等待第二级 KYC/产品审核",
            })

        for merchant in Merchant.objects.filter(is_deleted=False).select_related("kyc", "agent"):
            decision = policy.evaluate(merchant, include_usage=False)
            if merchant.status == Merchant.Status.ACTIVE and not decision.eligible:
                issues.append({
                    "severity": "ERROR",
                    "code": "ACTIVE_BUT_INELIGIBLE",
                    "merchant_no": merchant.merchant_no,
                    "message": "ACTIVE 商户不满足汇款准入条件",
                    "blockers": [item.as_dict() for item in decision.blockers],
                })
                if options["fix"]:
                    MerchantLifecycleService().suspend(
                        merchant,
                        reason_code="DATA_INCONSISTENT",
                        comment="生命周期审计发现 ACTIVE 商户不满足汇款准入条件",
                        actor="audit-command",
                        source="MANAGEMENT_COMMAND",
                    )

            active_accounts = merchant.nostro_accounts.filter(is_deleted=False).count()
            active_vas = merchant.virtual_accounts.filter(
                is_deleted=False, status="ACTIVE"
            ).count()
            if merchant.status != Merchant.Status.ACTIVE and (active_accounts or active_vas):
                issues.append({
                    "severity": "WARNING",
                    "code": "INACTIVE_WITH_ACTIVE_ACCOUNTS",
                    "merchant_no": merchant.merchant_no,
                    "message": "非 ACTIVE 商户仍有关联资金账户；保留历史资金能力但禁止新交易",
                    "nostro_accounts": active_accounts,
                    "active_virtual_accounts": active_vas,
                })

        summary = {
            "issue_count": len(issues),
            "fixed": bool(options["fix"]),
            "issues": issues,
        }
        if options["as_json"]:
            self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
            return

        self.stdout.write(f"发现 {len(issues)} 条生命周期审计记录")
        for issue in issues:
            self.stdout.write(
                f"[{issue['severity']}] {issue['code']} "
                f"{issue.get('merchant_no', '')} - {issue['message']}"
            )
        if options["fix"]:
            self.stdout.write(self.style.SUCCESS("安全修复已完成；未自动激活任何待审商户"))
