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

export const FEE_BEARING = {
  OUR: 'All charges to be borne by remitter',
  BEN: 'All charges to be borne by beneficiary',
  SHA: 'Charges to be borne by both remitter and beneficiary'
}

export const REMITTANCE_PURPOSES = [
  'Personal Consumption',
  'Household',
  'Bill Payment',
  'Payment For Goods',
  'Payment For Service',
  'Investment/Wealth Management',
  'Payment Of Loan',
  'Loan Lending',
  'Charity Donation',
  'Others'
]

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

export function formatMoneyCell(_row, _column, cellValue) {
  return money(cellValue)
}

export function datetime(v) {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  return d.toLocaleString('en-US', {
    year: 'numeric', month: 'short', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false
  })
}
