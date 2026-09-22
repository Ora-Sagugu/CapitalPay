"""Operations-console capability catalog.

Each item is a business a job title may be ticked for on Roles.
Page-level codes unlock the sidebar; write / approve / suspend / export /
freeze codes gate sensitive APIs. Super Admin bypasses these codes and is
not stored on RolePermission.
"""

from __future__ import annotations

ASSIGNABLE_ROLE_CODES = (
    "merchant_ops",
    "compliance",
    "finance",
    "support",
    "analyst",
)
SYSTEM_ROLE_CODES = ("super_admin",) + ASSIGNABLE_ROLE_CODES

OPS_ROLES = (
    {
        "code": "super_admin",
        "name": "Super Admin",
        "description": "Platform configuration, ops account permissions, high-risk approvals, and overall PSP oversight.",
    },
    {
        "code": "merchant_ops",
        "name": "Merchant Ops",
        "description": "Reviews merchant accounts, onboarding status, and service configuration; handles merchant ops issues.",
    },
    {
        "code": "compliance",
        "name": "Compliance / Risk",
        "description": "Reviews KYC/KYB outcomes, anomalies, fraud alerts, and risk cases; can restrict accounts.",
    },
    {
        "code": "finance",
        "name": "Finance",
        "description": "Monitors fees, settlement, wallet balances, transfers, and reconciliation; handles finance adjustments.",
    },
    {
        "code": "support",
        "name": "Customer Support",
        "description": "Investigates merchant issues using merchant, transaction, refund, settlement, and transfer records.",
    },
    {
        "code": "analyst",
        "name": "Analyst / Read-only",
        "description": "Views ops reports and analytics within authorized scope; cannot run sensitive business actions.",
    },
)

LEGACY_ROLE_MAP = {
    "maker": "merchant_ops",
    "checker": "compliance",
    "authoriser": "finance",
    "operator": "merchant_ops",
    "reviewer": "compliance",
    "approver": "finance",
}
RETIRED_ROLE_CODES = (
    "maker",
    "checker",
    "authoriser",
    "operator",
    "reviewer",
    "approver",
    "auditor",
    "merchant_admin",
)


def _cap(code, name, action, group, group_name, path, page, resource):
    return {
        "code": code,
        "name": name,
        "action": action,
        "group": group,
        "group_name": group_name,
        "path": path,
        "page": page,
        "resource": resource,
    }


OPS_CAPABILITIES = (
    _cap("feature:dashboard", "View overview", "view", "", "", "/dashboard", "feature:dashboard", "dashboard"),
    _cap("feature:reports", "View reports", "view", "", "", "/reports", "feature:reports", "report"),
    _cap("feature:reports.export", "Export reports", "export", "", "", "/reports", "feature:reports", "report"),
    _cap("feature:wallet", "View wallet", "view", "", "", "/wallet", "feature:wallet", "wallet"),
    _cap("feature:wallet.freeze", "Freeze / unfreeze wallet", "freeze", "", "", "/wallet", "feature:wallet", "wallet"),
    _cap("feature:merchants", "View customer profiles", "view", "customer", "Customers", "/merchants", "feature:merchants", "customer"),
    _cap("feature:merchants.write", "Create / edit customers", "write", "customer", "Customers", "/merchants", "feature:merchants", "customer"),
    _cap("feature:merchants.approve", "Approve / activate customers", "approve", "customer", "Customers", "/merchants", "feature:merchants", "customer"),
    _cap("feature:merchants.suspend", "Suspend / restrict customers", "suspend", "customer", "Customers", "/merchants", "feature:merchants", "customer"),
    _cap("feature:customers", "View end customers", "view", "customer", "Customers", "/customers", "feature:customers", "customer"),
    _cap("feature:virtual_accounts", "Manage virtual accounts", "manage", "customer", "Customers", "/virtual-accounts", "feature:virtual_accounts", "customer"),
    _cap("feature:deposits", "View deposits", "view", "customer", "Customers", "/deposits", "feature:deposits", "customer"),
    _cap("feature:deposits.approve", "Approve deposits", "approve", "customer", "Customers", "/deposits", "feature:deposits", "customer"),
    _cap("feature:fund_trace", "View fund trace", "view", "remittance", "Remittance", "/fund-trace", "feature:fund_trace", "remittance"),
    _cap("feature:orders", "View orders", "view", "remittance", "Remittance", "/orders", "feature:orders", "remittance"),
    _cap("feature:orders.approve", "Approve remittances", "approve", "remittance", "Remittance", "/orders", "feature:orders", "remittance"),
    _cap("feature:pre_orders", "View pre-orders", "view", "remittance", "Remittance", "/pre-orders", "feature:pre_orders", "remittance"),
    _cap("feature:refunds", "View refunds", "view", "remittance", "Remittance", "/refunds", "feature:refunds", "remittance"),
    _cap("feature:refunds.approve", "Approve refunds", "approve", "remittance", "Remittance", "/refunds", "feature:refunds", "remittance"),
    _cap("feature:exchange_rates", "Set FX rates", "set", "remittance", "Remittance", "/exchange-rates", "feature:exchange_rates", "remittance"),
    _cap("feature:remittance_fees", "Set remittance fee", "set", "remittance", "Remittance", "/remittance-fees", "feature:remittance_fees", "remittance"),
    _cap("feature:agents", "View agent profiles", "view", "agent", "Agents", "/agents", "feature:agents", "agent"),
    _cap("feature:agents.approve", "Approve agents", "approve", "agent", "Agents", "/agents", "feature:agents", "agent"),
    _cap("feature:agent_fees", "Set Agent Fee", "set", "agent", "Agents", "/agent-fees", "feature:agent_fees", "agent"),
    _cap("feature:disbursements", "View disbursements", "view", "agent", "Agents", "/disbursements", "feature:disbursements", "agent"),
    _cap("feature:disbursements.approve", "Approve disbursements", "approve", "agent", "Agents", "/disbursements", "feature:disbursements", "agent"),
    _cap("feature:banks", "Manage channels", "manage", "bank", "Banking", "/banks", "feature:banks", "bank"),
    _cap("feature:accounts", "Manage master account", "manage", "bank", "Banking", "/accounts", "feature:accounts", "bank"),
    _cap("feature:params", "Set parameters", "set", "bank", "Banking", "/params", "feature:params", "bank"),
    _cap("feature:bank_notifications", "View bank notifications", "view", "bank", "Banking", "/bank-notifications", "feature:bank_notifications", "bank"),
    _cap("feature:reconciliation", "Manage reconciliation", "manage", "bank", "Banking", "/reconciliation", "feature:reconciliation", "bank"),
    _cap("feature:fund_transfers", "Execute transfers", "manage", "bank", "Banking", "/fund-transfers", "feature:fund_transfers", "bank"),
    _cap("feature:adjustments", "View adjustments", "view", "bank", "Banking", "/adjustments", "feature:adjustments", "bank"),
    _cap("feature:adjustments.approve", "Approve adjustments", "approve", "bank", "Banking", "/adjustments", "feature:adjustments", "bank"),
    _cap("feature:sanctions", "Manage sanction lists", "manage", "sanction", "Sanctions", "/sanctions", "feature:sanctions", "sanction"),
    _cap("feature:scans", "View screening", "view", "sanction", "Sanctions", "/scans", "feature:scans", "sanction"),
    _cap("feature:risk_rating", "Set risk rating", "set", "sanction", "Sanctions", "/risk-rating", "feature:risk_rating", "sanction"),
    _cap("feature:roles", "Assign role functions", "manage", "system", "System", "/roles", "feature:roles", "system"),
    _cap("feature:users", "Manage operations users", "manage", "system", "System", "/users", "feature:users", "system"),
    _cap("feature:audit_logs", "View audit logs", "view", "system", "System", "/users", "feature:users", "system"),
)

# Default grants from docs/角色权限.csv (是 = action codes; 受限 = related view only).
# Extra read-only pages follow docs/角色(1).csv duties so menus are usable.
DEFAULT_ROLE_CAPABILITIES = {
    "merchant_ops": (
        "feature:dashboard",
        "feature:merchants",
        "feature:merchants.write",
        "feature:merchants.approve",
        "feature:customers",
        "feature:agents",
        "feature:agents.approve",
        "feature:virtual_accounts",
        "feature:deposits",
        "feature:fund_trace",
        "feature:orders",
        "feature:pre_orders",
        "feature:refunds",
        "feature:reports",
        "feature:audit_logs",
    ),
    "compliance": (
        "feature:dashboard",
        "feature:merchants",
        "feature:customers",
        "feature:agents",
        "feature:merchants.suspend",
        "feature:deposits",
        "feature:orders",
        "feature:fund_trace",
        "feature:reports",
        "feature:sanctions",
        "feature:scans",
        "feature:risk_rating",
        "feature:audit_logs",
    ),
    "finance": (
        "feature:dashboard",
        "feature:merchants",
        "feature:customers",
        "feature:wallet",
        "feature:deposits",
        "feature:fund_trace",
        "feature:orders",
        "feature:pre_orders",
        "feature:refunds",
        "feature:refunds.approve",
        "feature:remittance_fees",
        "feature:agent_fees",
        "feature:params",
        "feature:reconciliation",
        "feature:fund_transfers",
        "feature:adjustments",
        "feature:reports",
        "feature:reports.export",
        "feature:audit_logs",
        "feature:disbursements",
        "feature:exchange_rates",
    ),
    "support": (
        "feature:dashboard",
        "feature:merchants",
        "feature:customers",
        "feature:virtual_accounts",
        "feature:deposits",
        "feature:fund_trace",
        "feature:orders",
        "feature:pre_orders",
        "feature:refunds",
        "feature:disbursements",
        "feature:fund_transfers",
        "feature:reports",
        "feature:audit_logs",
        "feature:wallet",
    ),
    "analyst": (
        "feature:dashboard",
        "feature:merchants",
        "feature:customers",
        "feature:reports",
    ),
}

# Page-level aliases kept for callers that still import OPS_FUNCTIONS.
OPS_FUNCTIONS = OPS_CAPABILITIES

CAPABILITY_BY_CODE = {item["code"]: item for item in OPS_CAPABILITIES}
FUNCTION_BY_CODE = CAPABILITY_BY_CODE
FEATURE_CODES = tuple(item["code"] for item in OPS_CAPABILITIES)

APPROVE_BACKFILL_PAIRS = tuple(
    (item["page"], item["code"])
    for item in OPS_CAPABILITIES
    if item["action"] == "approve" and item["code"] != item["page"]
)

_PAGE_CODES: dict[str, list[str]] = {}
for _item in OPS_CAPABILITIES:
    _PAGE_CODES.setdefault(_item["page"], []).append(_item["code"])
PAGE_CAPABILITY_CODES = {page: tuple(codes) for page, codes in _PAGE_CODES.items()}


def codes_for_page(page_or_code: str) -> tuple[str, ...]:
    """All capability codes that unlock the same sidebar page."""
    spec = CAPABILITY_BY_CODE.get(page_or_code)
    page = spec["page"] if spec else page_or_code
    return PAGE_CAPABILITY_CODES.get(page, (page_or_code,))


def function_path_order():
    """Sidebar order used by the frontend fallback redirect."""
    seen = set()
    ordered = []
    for item in OPS_CAPABILITIES:
        if item["path"] in seen:
            continue
        seen.add(item["path"])
        ordered.append((item["path"], item["page"]))
    return ordered
