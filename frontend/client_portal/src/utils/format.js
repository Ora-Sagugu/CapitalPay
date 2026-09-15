export const ORDER_STATUS = {
  PENDING_AGENT_REVIEW: 'Awaiting agent review',
  PENDING_REVIEW: 'Awaiting operations review',
  PENDING_PAY: 'Awaiting funds',
  PAY_RECEIVED: 'Funds received',
  PENDING_SETTLE: 'Payout in progress',
  SETTLED: 'Completed',
  CLOSED: 'Closed',
  REFUNDING: 'Refund in progress',
  REFUNDED: 'Refunded',
  PRE_CREATE: 'Awaiting funds',
  PROCESSING: 'Awaiting funds',
  COMPLETED: 'Completed'
}

export const ORDER_STATUS_TYPE = {
  PENDING_AGENT_REVIEW: 'warning',
  PENDING_REVIEW: 'warning',
  PENDING_PAY: 'primary',
  PAY_RECEIVED: '',
  PENDING_SETTLE: 'warning',
  SETTLED: 'success',
  COMPLETED: 'success',
  CLOSED: 'info',
  REFUNDING: 'danger',
  REFUNDED: 'danger',
  PROCESSING: 'primary',
  PRE_CREATE: 'primary'
}

export const KYC_STATUS = {
  PENDING: 'Pending review',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  WARNING: 'Warning',
  DRAFT: 'Draft'
}

export const RISK_LEVEL = { LOW: 'Low risk', MEDIUM: 'Medium risk', HIGH: 'High risk', BLOCKED: 'Blocked' }
export const MERCHANT_STATUS = { ACTIVE: 'Active', SUSPENDED: 'Suspended', CLOSED: 'Closed', PENDING: 'Pending' }
export const AGENT_STATUS = { ACTIVE: 'Active', SUSPENDED: 'Suspended', CLOSED: 'Closed' }
export const DEPOSIT_STATUS = { PENDING: 'Pending review', APPROVED: 'Approved', REJECTED: 'Rejected' }
export const BANK_NOTIFICATION_STATUS = {
  RECEIVED: 'Received',
  MATCHED: 'Matched',
  MISMATCH: 'Amount mismatch',
  UNMATCHED: 'Unmatched'
}
export const ONBOARDING_STATUS = {
  none: 'Not submitted',
  pending: 'Pending review',
  under_review: 'Under review',
  approved: 'Approved',
  rejected: 'Rejected'
}
export const PAY_METHOD = { WIRE_TRANSFER: 'Wire transfer', ONLINE_BANK: 'Online banking', AUTHORIZED: 'Authorised payment' }
export const FEE_BEARING = {
  OUR: 'All charges to be borne by remitter',
  BEN: 'All charges to be borne by beneficiary',
  SHA: 'Charges to be borne by both remitter and beneficiary'
}
export const ROLE_NAME = {
  super_admin: 'Super Admin',
  maker: 'Maker',
  checker: 'Checker',
  authoriser: 'Authoriser',
  operator: 'Maker',
  reviewer: 'Checker',
  approver: 'Authoriser',
  agent: 'Agent',
  customer: 'Customer'
}

export function statusLabel(map, code) {
  if (!code) return '—'
  return map[code] || code
}

export function money(v, digits = 2) {
  if (v === null || v === undefined || v === '') return '0.00'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

const MONEY_FIELD_KEYS = new Set([
  'amount', 'total_amount', 'fee_amount', 'refund_amount', 'refund_fee_amount',
  'settle_amount', 'settle_net_amount', 'total_fee', 'channel_fee', 'platform_fee',
  'agent_fee', 'fee_total', 'fixed_fee', 'balance', 'sender_total', 'sender_fee',
  'beneficiary_fee', 'min_amount', 'max_amount', 'min_fee', 'max_fee',
  'commission_amount', 'amount_bank', 'amount_platform', 'daily_limit',
  'max_single_amount', 'platform_balance', 'bank_statement_balance',
  'total_refund_amount', 'net_amount', 'settled_amount', 'difference',
  'usd_balance', 'hkd_balance', 'cny_balance', 'ledger_balance',
  'available_balance', 'master_balance', 'virtual_accounts_total'
])

export function isMoneyField(key) {
  return MONEY_FIELD_KEYS.has(String(key || ''))
}

export function formatMoneyCell(_row, _column, cellValue) {
  return money(cellValue)
}

export function datetime(v) {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export function formatDate(v) {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v).slice(0, 10) || String(v)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function formatLongDate(d = new Date()) {
  return d.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

export function unwrapList(data) {
  if (Array.isArray(data)) return { rows: data, total: data.length }
  return {
    rows: data?.results || data?.items || [],
    total: data?.count ?? data?.total ?? 0
  }
}

export function mediaUrl(path) {
  if (!path) return ''
  if (/^https?:\/\//.test(path) || path.startsWith('/') || path.startsWith('data:')) return path
  return `/media/${path}`
}

export async function downloadMedia(path, filename) {
  if (!path) return
  const url = mediaUrl(path)
  const name = filename || path.split('/').pop() || 'download'
  if (path.startsWith('data:')) {
    const a = document.createElement('a')
    a.href = url
    a.download = name
    a.click()
    return
  }
  const res = await fetch(url)
  const blob = await res.blob()
  const blobUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = name
  a.click()
  URL.revokeObjectURL(blobUrl)
}

export const CURRENCIES = [
  { value: 'USD', label: 'US Dollar (USD)' },
  { value: 'EUR', label: 'Euro (EUR)' },
  { value: 'GBP', label: 'British Pound (GBP)' },
  { value: 'KES', label: 'Kenyan Shilling (KES)' },
  { value: 'NGN', label: 'Nigerian Naira (NGN)' },
  { value: 'ZAR', label: 'South African Rand (ZAR)' },
  { value: 'GHS', label: 'Ghanaian Cedi (GHS)' },
  { value: 'CNY', label: 'Chinese Yuan (CNY)' },
  { value: 'JPY', label: 'Japanese Yen (JPY)' },
  { value: 'HKD', label: 'Hong Kong Dollar (HKD)' }
]
