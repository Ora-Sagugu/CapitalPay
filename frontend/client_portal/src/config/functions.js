export const ASSIGNABLE_ROLES = [
  { code: 'maker', name: 'Maker' },
  { code: 'checker', name: 'Checker' },
  { code: 'authoriser', name: 'Authoriser' }
]

export const OPS_CAPABILITIES = [
  { code: 'feature:dashboard', name: 'View overview', action: 'view', group: '', groupName: '', path: '/dashboard', page: 'feature:dashboard' },
  { code: 'feature:reports', name: 'View reports', action: 'view', group: '', groupName: '', path: '/reports', page: 'feature:reports' },
  { code: 'feature:wallet', name: 'View wallet', action: 'view', group: '', groupName: '', path: '/wallet', page: 'feature:wallet' },
  { code: 'feature:merchants', name: 'View customer profiles', action: 'view', group: 'customer', groupName: 'Customers', path: '/merchants', page: 'feature:merchants' },
  { code: 'feature:merchants.approve', name: 'Approve customers', action: 'approve', group: 'customer', groupName: 'Customers', path: '/merchants', page: 'feature:merchants' },
  { code: 'feature:virtual_accounts', name: 'Manage virtual accounts', action: 'manage', group: 'customer', groupName: 'Customers', path: '/virtual-accounts', page: 'feature:virtual_accounts' },
  { code: 'feature:deposits', name: 'View deposits', action: 'view', group: 'customer', groupName: 'Customers', path: '/deposits', page: 'feature:deposits' },
  { code: 'feature:deposits.approve', name: 'Approve deposits', action: 'approve', group: 'customer', groupName: 'Customers', path: '/deposits', page: 'feature:deposits' },
  { code: 'feature:fund_trace', name: 'View fund trace', action: 'view', group: 'remittance', groupName: 'Remittance', path: '/fund-trace', page: 'feature:fund_trace' },
  { code: 'feature:orders', name: 'View orders', action: 'view', group: 'remittance', groupName: 'Remittance', path: '/orders', page: 'feature:orders' },
  { code: 'feature:orders.approve', name: 'Approve remittances', action: 'approve', group: 'remittance', groupName: 'Remittance', path: '/orders', page: 'feature:orders' },
  { code: 'feature:pre_orders', name: 'View pre-orders', action: 'view', group: 'remittance', groupName: 'Remittance', path: '/pre-orders', page: 'feature:pre_orders' },
  { code: 'feature:refunds', name: 'View refunds', action: 'view', group: 'remittance', groupName: 'Remittance', path: '/refunds', page: 'feature:refunds' },
  { code: 'feature:refunds.approve', name: 'Approve refunds', action: 'approve', group: 'remittance', groupName: 'Remittance', path: '/refunds', page: 'feature:refunds' },
  { code: 'feature:exchange_rates', name: 'Set FX rates', action: 'set', group: 'remittance', groupName: 'Remittance', path: '/exchange-rates', page: 'feature:exchange_rates' },
  { code: 'feature:remittance_fees', name: 'Set remittance fee', action: 'set', group: 'remittance', groupName: 'Remittance', path: '/remittance-fees', page: 'feature:remittance_fees' },
  { code: 'feature:agents', name: 'View agent profiles', action: 'view', group: 'agent', groupName: 'Agents', path: '/agents', page: 'feature:agents' },
  { code: 'feature:agents.approve', name: 'Approve agents', action: 'approve', group: 'agent', groupName: 'Agents', path: '/agents', page: 'feature:agents' },
  { code: 'feature:agent_fees', name: 'Set Agent Fee', action: 'set', group: 'agent', groupName: 'Agents', path: '/agent-fees', page: 'feature:agent_fees' },
  { code: 'feature:disbursements', name: 'View disbursements', action: 'view', group: 'agent', groupName: 'Agents', path: '/disbursements', page: 'feature:disbursements' },
  { code: 'feature:disbursements.approve', name: 'Approve disbursements', action: 'approve', group: 'agent', groupName: 'Agents', path: '/disbursements', page: 'feature:disbursements' },
  { code: 'feature:banks', name: 'Manage channels', action: 'manage', group: 'bank', groupName: 'Banking', path: '/banks', page: 'feature:banks' },
  { code: 'feature:accounts', name: 'Manage master account', action: 'manage', group: 'bank', groupName: 'Banking', path: '/accounts', page: 'feature:accounts' },
  { code: 'feature:params', name: 'Set parameters', action: 'set', group: 'bank', groupName: 'Banking', path: '/params', page: 'feature:params' },
  { code: 'feature:bank_notifications', name: 'View bank notifications', action: 'view', group: 'bank', groupName: 'Banking', path: '/bank-notifications', page: 'feature:bank_notifications' },
  { code: 'feature:reconciliation', name: 'Manage reconciliation', action: 'manage', group: 'bank', groupName: 'Banking', path: '/reconciliation', page: 'feature:reconciliation' },
  { code: 'feature:fund_transfers', name: 'Execute transfers', action: 'manage', group: 'bank', groupName: 'Banking', path: '/fund-transfers', page: 'feature:fund_transfers' },
  { code: 'feature:adjustments', name: 'View adjustments', action: 'view', group: 'bank', groupName: 'Banking', path: '/adjustments', page: 'feature:adjustments' },
  { code: 'feature:adjustments.approve', name: 'Approve adjustments', action: 'approve', group: 'bank', groupName: 'Banking', path: '/adjustments', page: 'feature:adjustments' },
  { code: 'feature:sanctions', name: 'Manage sanction lists', action: 'manage', group: 'sanction', groupName: 'Sanctions', path: '/sanctions', page: 'feature:sanctions' },
  { code: 'feature:scans', name: 'View screening', action: 'view', group: 'sanction', groupName: 'Sanctions', path: '/scans', page: 'feature:scans' },
  { code: 'feature:risk_rating', name: 'Set risk rating', action: 'set', group: 'sanction', groupName: 'Sanctions', path: '/risk-rating', page: 'feature:risk_rating' },
  { code: 'feature:roles', name: 'Assign role businesses', action: 'manage', group: 'system', groupName: 'System', path: '/roles', page: 'feature:roles' },
  { code: 'feature:users', name: 'Manage operations users', action: 'manage', group: 'system', groupName: 'System', path: '/users', page: 'feature:users' }
]

const PAGE_CODES = {}
for (const cap of OPS_CAPABILITIES) {
  if (!PAGE_CODES[cap.page]) PAGE_CODES[cap.page] = []
  PAGE_CODES[cap.page].push(cap.code)
}

export const OPS_FUNCTIONS = (() => {
  const seen = new Set()
  const pages = []
  for (const cap of OPS_CAPABILITIES) {
    if (seen.has(cap.path)) continue
    seen.add(cap.path)
    pages.push({
      code: cap.page,
      name: cap.name,
      group: cap.group,
      groupName: cap.groupName,
      path: cap.path
    })
  }
  return pages
})()

export function codesForPage(page) {
  return PAGE_CODES[page] || [page]
}

export function isSuperAdmin(roles) {
  const list = roles || []
  return list.includes('super_admin') || list.some((r) => (r?.code || r) === 'super_admin')
}

export function permissionCodes(user) {
  return (user?.permissions || []).map((p) => p?.code || p)
}

export function firstAllowedPath(user) {
  if (isSuperAdmin(user?.roles)) return '/dashboard'
  const perms = new Set(permissionCodes(user))
  const hit = OPS_CAPABILITIES.find((fn) => perms.has(fn.code))
  return hit ? hit.path : '/no-access'
}

export function canAccessPath(user, permission) {
  if (!permission) return true
  if (isSuperAdmin(user?.roles)) return true
  const perms = permissionCodes(user)
  const wanted = codesForPage(permission)
  return wanted.some((code) => perms.includes(code))
}
