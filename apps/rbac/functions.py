"""Operations-console capability catalog.

Each item is a business a job title may be ticked for on Roles.
Page-level codes unlock the sidebar; `.approve` codes gate review/execute APIs.
Super Admin bypasses these codes and is not stored on RolePermission.
"""

from __future__ import annotations

ASSIGNABLE_ROLE_CODES = ("maker", "checker", "authoriser")
SYSTEM_ROLE_CODES = ("super_admin",) + ASSIGNABLE_ROLE_CODES

OPS_ROLES = (
    {
        "code": "super_admin",
        "name": "Super Admin",
        "description": "Always has every business. Capabilities cannot be changed.",
    },
    {
        "code": "maker",
        "name": "Maker",
        "description": "Performs the businesses ticked for this title.",
    },
    {
        "code": "checker",
        "name": "Checker",
        "description": "Performs the businesses ticked for this title.",
    },
    {
        "code": "authoriser",
        "name": "Authoriser",
        "description": "Performs the businesses ticked for this title.",
    },
)

LEGACY_ROLE_MAP = {
    "operator": "maker",
    "reviewer": "checker",
    "approver": "authoriser",
}
RETIRED_ROLE_CODES = (
    "operator",
    "reviewer",
    "approver",
    "finance",
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
    _cap("feature:wallet", "View wallet", "view", "", "", "/wallet", "feature:wallet", "wallet"),
    _cap("feature:merchants", "View customer profiles", "view", "customer", "Customers", "/merchants", "feature:merchants", "customer"),
    _cap("feature:merchants.approve", "Approve customers", "approve", "customer", "Customers", "/merchants", "feature:merchants", "customer"),
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
    _cap("feature:roles", "Assign role businesses", "manage", "system", "System", "/roles", "feature:roles", "system"),
    _cap("feature:users", "Manage operations users", "manage", "system", "System", "/users", "feature:users", "system"),
)

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
