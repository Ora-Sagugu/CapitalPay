/** Canonical projection of inbound card-platform objects and events.

This portal records the projection. It does not capture, refund, or fight
chargebacks. Unknown provider types map to UNKNOWN and keep raw_type.
*/

export const CARD_FAMILY = {
  CHECKOUT: 'CHECKOUT',
  REFUND: 'REFUND',
  CHARGEBACK: 'CHARGEBACK'
}

export const CARD_EVENT_TYPE = {
  CHECKOUT_CREATED: 'CHECKOUT_CREATED',
  AUTHORIZED: 'AUTHORIZED',
  CAPTURED: 'CAPTURED',
  DECLINED: 'DECLINED',
  VOIDED: 'VOIDED',
  EXPIRED: 'EXPIRED',
  REFUND_PENDING: 'REFUND_PENDING',
  REFUND_SUCCEEDED: 'REFUND_SUCCEEDED',
  REFUND_FAILED: 'REFUND_FAILED',
  REFUND_REVERSED: 'REFUND_REVERSED',
  RFI: 'RFI',
  PRESENTMENT: 'PRESENTMENT',
  FIRST_CHARGEBACK: 'FIRST_CHARGEBACK',
  REPRESENTMENT: 'REPRESENTMENT',
  SECOND_CHARGEBACK: 'SECOND_CHARGEBACK',
  ARBITRATION: 'ARBITRATION',
  UNKNOWN: 'UNKNOWN'
}

export const CARD_FAMILY_TYPES = {
  [CARD_FAMILY.CHECKOUT]: [
    CARD_EVENT_TYPE.CHECKOUT_CREATED,
    CARD_EVENT_TYPE.AUTHORIZED,
    CARD_EVENT_TYPE.CAPTURED,
    CARD_EVENT_TYPE.DECLINED,
    CARD_EVENT_TYPE.VOIDED,
    CARD_EVENT_TYPE.EXPIRED
  ],
  [CARD_FAMILY.REFUND]: [
    CARD_EVENT_TYPE.REFUND_PENDING,
    CARD_EVENT_TYPE.REFUND_SUCCEEDED,
    CARD_EVENT_TYPE.REFUND_FAILED,
    CARD_EVENT_TYPE.REFUND_REVERSED
  ],
  [CARD_FAMILY.CHARGEBACK]: [
    CARD_EVENT_TYPE.RFI,
    CARD_EVENT_TYPE.PRESENTMENT,
    CARD_EVENT_TYPE.FIRST_CHARGEBACK,
    CARD_EVENT_TYPE.REPRESENTMENT,
    CARD_EVENT_TYPE.SECOND_CHARGEBACK,
    CARD_EVENT_TYPE.ARBITRATION
  ]
}

const TYPE_TO_FAMILY = Object.fromEntries(
  Object.entries(CARD_FAMILY_TYPES).flatMap(([family, types]) => types.map((type) => [type, family]))
)

/** Common PSP / issuer aliases → canonical type. Unlisted values stay UNKNOWN. */
export const CARD_TYPE_ALIASES = {
  PAYMENT_CREATED: CARD_EVENT_TYPE.CHECKOUT_CREATED,
  PAYMENT_AUTHORIZED: CARD_EVENT_TYPE.AUTHORIZED,
  PAYMENT_CAPTURED: CARD_EVENT_TYPE.CAPTURED,
  PAYMENT_DECLINED: CARD_EVENT_TYPE.DECLINED,
  PAYMENT_VOIDED: CARD_EVENT_TYPE.VOIDED,
  PAYMENT_EXPIRED: CARD_EVENT_TYPE.EXPIRED,
  AUTHORIZATION: CARD_EVENT_TYPE.AUTHORIZED,
  CAPTURE: CARD_EVENT_TYPE.CAPTURED,
  REFUND: CARD_EVENT_TYPE.REFUND_SUCCEEDED,
  CHARGE_DISPUTE_CREATED: CARD_EVENT_TYPE.FIRST_CHARGEBACK,
  CHARGE_DISPUTE_CLOSED: CARD_EVENT_TYPE.ARBITRATION,
  NOTIFICATION_OF_CHARGEBACK: CARD_EVENT_TYPE.FIRST_CHARGEBACK,
  CHARGEBACK_OPENED: CARD_EVENT_TYPE.FIRST_CHARGEBACK,
  FIRST_PRESENTMENT: CARD_EVENT_TYPE.PRESENTMENT,
  SECOND_PRESENTMENT: CARD_EVENT_TYPE.REPRESENTMENT,
  PRE_ARBITRATION: CARD_EVENT_TYPE.SECOND_CHARGEBACK,
  PREARBITRATION: CARD_EVENT_TYPE.SECOND_CHARGEBACK,
  ARBITRATION_OPENED: CARD_EVENT_TYPE.ARBITRATION,
  REQUEST_FOR_INFORMATION: CARD_EVENT_TYPE.RFI
}

/**
 * Merchant-initiated card refunds come in two commercial shapes:
 * - MONEY_ONLY: refund the payment (no goods return)
 * - WITH_GOODS: refund the payment and take the goods back
 */
export const CARD_REFUND_KIND = {
  MONEY_ONLY: 'MONEY_ONLY',
  WITH_GOODS: 'WITH_GOODS'
}

const REFUND_KIND_ALIASES = {
  MONEY_ONLY: CARD_REFUND_KIND.MONEY_ONLY,
  REFUND_ONLY: CARD_REFUND_KIND.MONEY_ONLY,
  PURE_REFUND: CARD_REFUND_KIND.MONEY_ONLY,
  MONEY: CARD_REFUND_KIND.MONEY_ONLY,
  WITH_GOODS: CARD_REFUND_KIND.WITH_GOODS,
  WITH_RETURN: CARD_REFUND_KIND.WITH_GOODS,
  RETURN_GOODS: CARD_REFUND_KIND.WITH_GOODS,
  GOODS_RETURN: CARD_REFUND_KIND.WITH_GOODS,
  MERCHANDISE_RETURN: CARD_REFUND_KIND.WITH_GOODS,
  RETURN: CARD_REFUND_KIND.WITH_GOODS
}

export function canonicalRefundKind(raw, family) {
  if (family !== CARD_FAMILY.REFUND) return null
  if (raw?.refund_kind != null) {
    const key = String(raw.refund_kind).trim().toUpperCase().replace(/[.\s-]+/g, '_')
    if (CARD_REFUND_KIND[key]) return CARD_REFUND_KIND[key]
    if (REFUND_KIND_ALIASES[key]) return REFUND_KIND_ALIASES[key]
  }
  if (raw?.goods_return === true || raw?.return_goods === true || raw?.with_goods === true) {
    return CARD_REFUND_KIND.WITH_GOODS
  }
  if (raw?.goods_return === false || raw?.return_goods === false || raw?.with_goods === false) {
    return CARD_REFUND_KIND.MONEY_ONLY
  }
  return CARD_REFUND_KIND.MONEY_ONLY
}

/** Scheme cycle for a chargeback-path type. RFI and terminals are unscoped. */
export const CHARGEBACK_CYCLE = {
  [CARD_EVENT_TYPE.PRESENTMENT]: 1,
  [CARD_EVENT_TYPE.FIRST_CHARGEBACK]: 1,
  [CARD_EVENT_TYPE.REPRESENTMENT]: 2,
  [CARD_EVENT_TYPE.SECOND_CHARGEBACK]: 2,
  [CARD_EVENT_TYPE.ARBITRATION]: 3
}

export function chargebackCycle(type) {
  return CHARGEBACK_CYCLE[type] || null
}

export const CARD_BUCKET = {
  AVAILABLE: 'available',
  PENDING: 'pending',
  RESERVED: 'reserved',
  DISPUTE_HOLD: 'dispute_hold'
}

export const CARD_BUCKETS = [
  CARD_BUCKET.AVAILABLE,
  CARD_BUCKET.PENDING,
  CARD_BUCKET.RESERVED,
  CARD_BUCKET.DISPUTE_HOLD
]

const CHECKOUT_OPEN = new Set([CARD_EVENT_TYPE.CHECKOUT_CREATED, CARD_EVENT_TYPE.AUTHORIZED])
const CHECKOUT_CLOSED = new Set([
  CARD_EVENT_TYPE.CAPTURED,
  CARD_EVENT_TYPE.DECLINED,
  CARD_EVENT_TYPE.VOIDED,
  CARD_EVENT_TYPE.EXPIRED
])
const REFUND_OPEN = new Set([CARD_EVENT_TYPE.REFUND_PENDING])
const REFUND_CLOSED = new Set([
  CARD_EVENT_TYPE.REFUND_SUCCEEDED,
  CARD_EVENT_TYPE.REFUND_FAILED,
  CARD_EVENT_TYPE.REFUND_REVERSED
])
const DISPUTE_OPEN = new Set([
  CARD_EVENT_TYPE.RFI,
  CARD_EVENT_TYPE.PRESENTMENT,
  CARD_EVENT_TYPE.FIRST_CHARGEBACK,
  CARD_EVENT_TYPE.REPRESENTMENT,
  CARD_EVENT_TYPE.SECOND_CHARGEBACK
])
const DISPUTE_CLOSED = new Set([
  CARD_EVENT_TYPE.ARBITRATION
])

export function cardDec(v) {
  return Number(v || 0)
}

export function cardFmt(n) {
  return (Math.round(Number(n) * 100) / 100).toFixed(2)
}

/** Deterministic “scheme” coin-flip for arbitration credit vs debit. */
export function arbitrationMoneyDirection(seed) {
  const text = String(seed || '')
  let hash = 0
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 31 + text.charCodeAt(i)) >>> 0
  }
  return hash % 2 === 0 ? 'CREDIT' : 'DEBIT'
}

/**
 * Chargeback money-flow convention (merchant available balance):
 * Presentment / Representment → +
 * 1st / 2nd Chargeback → −
 * Arbitration → scheme outcome (CREDIT or DEBIT)
 */
export function chargebackLedgerEffects(type, amount, seed = '') {
  const value = cardFmt(amount)
  if (!cardDec(value)) return []
  if (type === CARD_EVENT_TYPE.PRESENTMENT || type === CARD_EVENT_TYPE.REPRESENTMENT) {
    return [{ bucket: CARD_BUCKET.AVAILABLE, direction: 'CREDIT', amount: value }]
  }
  if (type === CARD_EVENT_TYPE.FIRST_CHARGEBACK || type === CARD_EVENT_TYPE.SECOND_CHARGEBACK) {
    return [{ bucket: CARD_BUCKET.AVAILABLE, direction: 'DEBIT', amount: value }]
  }
  if (type === CARD_EVENT_TYPE.ARBITRATION) {
    return [{
      bucket: CARD_BUCKET.AVAILABLE,
      direction: arbitrationMoneyDirection(seed),
      amount: value
    }]
  }
  return []
}

export function familyOf(type) {
  return TYPE_TO_FAMILY[type] || ''
}

export function canonicalType(rawType) {
  const key = String(rawType || '')
    .trim()
    .toUpperCase()
    .replace(/[.\s-]+/g, '_')
  if (CARD_EVENT_TYPE[key]) return CARD_EVENT_TYPE[key]
  return CARD_TYPE_ALIASES[key] || CARD_EVENT_TYPE.UNKNOWN
}

function canonicalStatus(rawStatus, type) {
  if (!rawStatus) return type
  const mapped = canonicalType(rawStatus)
  return mapped === CARD_EVENT_TYPE.UNKNOWN ? rawStatus : mapped
}

export function normalizeLedgerEffects(effects) {
  if (!Array.isArray(effects)) return []
  return effects
    .filter((item) => item && item.direction && item.bucket && item.amount != null)
    .map((item) => ({
      bucket: CARD_BUCKETS.includes(item.bucket) ? item.bucket : CARD_BUCKET.AVAILABLE,
      direction: item.direction === 'CREDIT' ? 'CREDIT' : 'DEBIT',
      amount: cardFmt(item.amount)
    }))
}

export function primaryLedgerEffect(event) {
  const effects = event?.ledger_effects || []
  return effects.find((item) => item.bucket === CARD_BUCKET.AVAILABLE) || effects[0] || null
}

export function hasMoneyMovement(event) {
  return (event?.ledger_effects || []).length > 0
}

export function eventDirection(event) {
  return primaryLedgerEffect(event)?.direction || null
}

export function eventAmount(event) {
  const effect = primaryLedgerEffect(event)
  if (effect) return effect.amount
  return cardFmt(event?.amount)
}

export function normalizeCardBalance(row = {}) {
  const available = cardFmt(row.available)
  const pending = cardFmt(row.pending)
  const reserved = cardFmt(row.reserved ?? row.frozen)
  const disputeHold = cardFmt(row.dispute_hold)
  const ledger = row.ledger != null || row.balance != null
    ? cardFmt(row.ledger ?? row.balance)
    : cardFmt(cardDec(available) + cardDec(pending) + cardDec(reserved) + cardDec(disputeHold))
  return {
    currency: (row.currency || '').toUpperCase(),
    status: row.status || 'ACTIVE',
    available,
    pending,
    reserved,
    dispute_hold: disputeHold,
    frozen: reserved,
    ledger,
    balance: ledger
  }
}

export function normalizeCardEvent(raw = {}) {
  const rawType = raw.raw_type || raw.type || ''
  const type = canonicalType(raw.type || raw.raw_type)
  const family = raw.family && CARD_FAMILY[raw.family] ? raw.family : familyOf(type)
  let ledgerEffects = normalizeLedgerEffects(raw.ledger_effects)
  if (family === CARD_FAMILY.CHARGEBACK) {
    const enforced = chargebackLedgerEffects(
      type,
      raw.amount,
      raw.id || raw.dispute_id || raw.payment_id || rawType
    )
    if (enforced.length) ledgerEffects = enforced
  }
  const occurredAt = raw.occurred_at || raw.created_at || ''
  const refundKind = canonicalRefundKind(raw, family)
  return {
    id: raw.id,
    family,
    type,
    raw_type: rawType || type,
    object_id: raw.object_id || raw.payment_id || raw.refund_id || raw.dispute_id || raw.id,
    payment_id: raw.payment_id || null,
    refund_id: raw.refund_id || null,
    dispute_id: raw.dispute_id || null,
    refund_kind: refundKind,
    scheme: raw.scheme || '',
    last4: raw.last4 || '',
    currency: (raw.currency || '').toUpperCase(),
    amount: raw.amount != null ? cardFmt(raw.amount) : eventAmount({ ledger_effects: ledgerEffects, amount: 0 }),
    status: canonicalStatus(raw.status, type),
    occurred_at: occurredAt,
    created_at: occurredAt,
    remark: raw.remark || '',
    reason_code: raw.reason_code || '',
    provider: raw.provider || '',
    ledger_effects: ledgerEffects,
    balance_after: raw.balance_after != null ? cardFmt(raw.balance_after) : ''
  }
}

export function maskCard(item) {
  if (!item?.last4) return ''
  const scheme = item.scheme ? `${item.scheme} ` : ''
  return `${scheme}••${item.last4}`
}

function latestByKey(events, keyOf, openSet, closedSet) {
  const latest = new Map()
  for (const event of events) {
    const key = keyOf(event)
    if (!key) continue
    if (!openSet.has(event.type) && !closedSet.has(event.type)) continue
    const prev = latest.get(key)
    if (!prev || new Date(event.occurred_at) >= new Date(prev.occurred_at)) latest.set(key, event)
  }
  let open = 0
  for (const event of latest.values()) {
    if (openSet.has(event.type)) open += 1
  }
  return open
}

export function cardEventSummary(events = []) {
  const normalized = events.map(normalizeCardEvent)
  return {
    openCheckouts: latestByKey(
      normalized,
      (event) => event.payment_id,
      CHECKOUT_OPEN,
      CHECKOUT_CLOSED
    ),
    openRefunds: latestByKey(
      normalized,
      (event) => event.refund_id || event.object_id,
      REFUND_OPEN,
      REFUND_CLOSED
    ),
    openChargebacks: latestByKey(
      normalized,
      (event) => event.dispute_id || event.object_id,
      DISPUTE_OPEN,
      DISPUTE_CLOSED
    )
  }
}

export function eventsForPayment(events = [], paymentId) {
  if (!paymentId) return []
  return events
    .map(normalizeCardEvent)
    .filter((event) => event.payment_id === paymentId)
    .sort((a, b) => new Date(a.occurred_at) - new Date(b.occurred_at))
}

/**
 * Chargeback cycle shown in the payment timeline drawer.
 * Only these five scheme steps — no checkout, refund, RFI, or outcome events.
 */
export const PAYMENT_CHARGEBACK_PATH = [
  CARD_EVENT_TYPE.PRESENTMENT,
  CARD_EVENT_TYPE.FIRST_CHARGEBACK,
  CARD_EVENT_TYPE.REPRESENTMENT,
  CARD_EVENT_TYPE.SECOND_CHARGEBACK,
  CARD_EVENT_TYPE.ARBITRATION
]

function appendChargebackPath(steps, events, { disputeId = '', untilType = '' } = {}) {
  const groups = new Map()
  for (const event of events) {
    if (!PAYMENT_CHARGEBACK_PATH.includes(event.type)) continue
    const key = event.dispute_id || event.object_id || event.id
    if (disputeId && key !== disputeId) continue
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(event)
  }
  for (const groupEvents of groups.values()) {
    let reachedIdx = -1
    PAYMENT_CHARGEBACK_PATH.forEach((type, idx) => {
      if (groupEvents.some((event) => event.type === type)) reachedIdx = idx
    })
    if (untilType) {
      const untilIdx = PAYMENT_CHARGEBACK_PATH.indexOf(untilType)
      if (untilIdx >= 0) reachedIdx = Math.min(reachedIdx, untilIdx)
    }
    for (let i = 0; i <= reachedIdx; i += 1) {
      const type = PAYMENT_CHARGEBACK_PATH[i]
      const event = groupEvents.find((item) => item.type === type)
      if (!event) continue
      steps.push({
        key: `${type}-${event.id}`,
        type,
        family: familyOf(type),
        event,
        phase: 'chargeback',
        cycle: chargebackCycle(type)
      })
    }
  }
}

/**
 * Build the chargeback cycle shown in the drawer.
 * Only Presentment → 1st CB → Representment → 2nd CB → Arbitration,
 * as far as the selected step (or farthest event if none selected).
 */
export function paymentFlowTimeline(events = [], paymentId, options = {}) {
  const paymentEvents = eventsForPayment(events, paymentId)
  if (!paymentEvents.length) return []

  const steps = []
  appendChargebackPath(steps, paymentEvents, options)

  steps.sort((a, b) => {
    const ta = new Date(a.event?.occurred_at || 0).getTime()
    const tb = new Date(b.event?.occurred_at || 0).getTime()
    if (ta !== tb) return ta - tb
    return String(a.key).localeCompare(String(b.key))
  })

  return steps.map((step, idx) => ({
    ...step,
    cycle: step.cycle ?? chargebackCycle(step.type),
    isLast: idx === steps.length - 1,
    isTerminal: step.type === CARD_EVENT_TYPE.ARBITRATION
  }))
}

export function statusTagType(status) {
  const value = String(status || '').toUpperCase()
  if (['CAPTURED', 'REFUND_SUCCEEDED', 'SUCCESS', 'ACTIVE', 'SETTLEMENT'].includes(value)) {
    return 'success'
  }
  if (['DECLINED', 'REFUND_FAILED', 'EXPIRED', 'FAILED'].includes(value)) {
    return 'danger'
  }
  if ([
    'AUTHORIZED',
    'CHECKOUT_CREATED',
    'REFUND_PENDING',
    'FIRST_CHARGEBACK',
    'RFI',
    'REPRESENTMENT',
    'SECOND_CHARGEBACK',
    'ARBITRATION',
    'PENDING',
    'FROZEN'
  ].includes(value)) {
    return 'warning'
  }
  return 'info'
}
