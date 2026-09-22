/** Exhibition fixtures for demo Merchant / Agent portal funding rails. */

export const EXHIBITION_EMAILS = new Set([
  'lilysky@qq.com',
  'gracenyambura@gmail.com',
  'tomlee@gmail.com',
  'amyfox@gmail.com',
  'miaagrey@gmail.com'
])

const MIAA_GREY_EMAIL = 'miaagrey@gmail.com'

export function exhibitionUserEmail(user) {
  return (user?.email || '').toLowerCase().trim()
}

export function isExhibitionUser(user) {
  return EXHIBITION_EMAILS.has(exhibitionUserEmail(user))
}

export function isMiaaGreyUser(user) {
  const email = exhibitionUserEmail(user)
  const username = (user?.username || '').toLowerCase().trim()
  return email === MIAA_GREY_EMAIL || username === 'miaagrey'
}

/** @deprecated Prefer isExhibitionUser — Agents and Merchants are peers. */
export function isExhibitionMerchant(user) {
  return isExhibitionUser(user)
}

export function exhibitionWallets(user) {
  if (isMiaaGreyUser(user)) return []
  return [
    { currency: 'USD', balance: '18600.00', available: '17200.00', frozen: '1400.00', status: 'ACTIVE' },
    { currency: 'EUR', balance: '5400.00', available: '5400.00', frozen: '0.00', status: 'ACTIVE' },
    { currency: 'CNY', balance: '98000.00', available: '92000.00', frozen: '6000.00', status: 'ACTIVE' }
  ]
}

export function exhibitionWalletTxns(user) {
  if (isMiaaGreyUser(user)) return []
  return [
    {
      id: 'WTX-LILY-001',
      type: 'TOP_UP',
      currency: 'USD',
      amount: '8000.00',
      balance_after: '18600.00',
      status: 'SUCCESS',
      created_at: '2026-09-14T08:20:00Z',
      remark: 'Alipay-style top-up to CapitalPay'
    },
    {
      id: 'WTX-LILY-002',
      type: 'TRANSFER_OUT',
      currency: 'USD',
      amount: '2500.00',
      balance_after: '16100.00',
      status: 'SUCCESS',
      created_at: '2026-09-15T11:05:00Z',
      remark: 'Remittance funding PAYLILYSKY02'
    },
    {
      id: 'WTX-LILY-003',
      type: 'FREEZE',
      currency: 'USD',
      amount: '1400.00',
      balance_after: '18600.00',
      status: 'SUCCESS',
      created_at: '2026-09-16T03:40:00Z',
      remark: 'Hold for pending remittance'
    },
    {
      id: 'WTX-LILY-004',
      type: 'TOP_UP',
      currency: 'CNY',
      amount: '50000.00',
      balance_after: '98000.00',
      status: 'SUCCESS',
      created_at: '2026-09-12T06:15:00Z',
      remark: 'Wallet top-up'
    }
  ]
}

export function exhibitionCardInstruments(user) {
  if (isMiaaGreyUser(user)) return miaaCardInstruments()
  return [
    { id: 'card-visa-4242', scheme: 'Visa', last4: '4242', status: 'ACTIVE' },
    { id: 'card-mc-4444', scheme: 'Mastercard', last4: '4444', status: 'ACTIVE' }
  ]
}

export function exhibitionCards(user) {
  if (isMiaaGreyUser(user)) return miaaCards()
  return [
    {
      currency: 'USD',
      available: '9400.00',
      pending: '0.00',
      reserved: '0.00',
      dispute_hold: '350.00',
      ledger: '9750.00',
      status: 'ACTIVE'
    }
  ]
}

export function exhibitionCardTxns(user) {
  if (isMiaaGreyUser(user)) return miaaCardTxns()
  return lilyCardTxns()
}

function miaaCardInstruments() {
  return [
    { id: 'card-miaa-visa-4242', scheme: 'Visa', last4: '4242', status: 'ACTIVE' },
    { id: 'card-miaa-mc-5555', scheme: 'Mastercard', last4: '5555', status: 'ACTIVE' }
  ]
}

function miaaCards() {
  return [
    {
      currency: 'USD',
      available: '6680.00',
      pending: '0.00',
      reserved: '0.00',
      dispute_hold: '0.00',
      ledger: '6680.00',
      status: 'ACTIVE'
    }
  ]
}

/** Checkout / Refund (2 each) + Chargeback cycle for Miaa Grey.
 * Signs: Presentment/Representment +, 1st/2nd Chargeback -, Arbitration scheme coin-flip.
 */
function miaaCardTxns() {
  return [
    {
      id: 'CEV-MIAA-012',
      type: 'ARBITRATION',
      payment_id: 'PAY-MIAA-CHK-004',
      dispute_id: 'DSP-MIAA-004',
      scheme: 'Mastercard',
      last4: '5555',
      currency: 'USD',
      amount: '260.00',
      status: 'ARBITRATION',
      reason_code: '10.4',
      occurred_at: '2026-09-19T08:00:00Z',
      remark: 'Card scheme arbitration outcome',
      raw_type: 'arbitration.opened',
      provider: 'mastercard'
    },
    {
      id: 'CEV-MIAA-011',
      type: 'SECOND_CHARGEBACK',
      payment_id: 'PAY-MIAA-CHK-004',
      dispute_id: 'DSP-MIAA-004',
      scheme: 'Mastercard',
      last4: '5555',
      currency: 'USD',
      amount: '260.00',
      status: 'SECOND_CHARGEBACK',
      reason_code: '10.4',
      occurred_at: '2026-09-18T10:00:00Z',
      remark: 'Issuer returned a 2nd chargeback after representment',
      raw_type: 'pre_arbitration',
      provider: 'mastercard'
    },
    {
      id: 'CEV-MIAA-010',
      type: 'REPRESENTMENT',
      payment_id: 'PAY-MIAA-CHK-004',
      dispute_id: 'DSP-MIAA-004',
      scheme: 'Mastercard',
      last4: '5555',
      currency: 'USD',
      amount: '260.00',
      status: 'REPRESENTMENT',
      reason_code: '10.4',
      occurred_at: '2026-09-17T14:20:00Z',
      remark: 'Merchant represented with shipping evidence',
      raw_type: 'second.presentment',
      provider: 'mastercard'
    },
    {
      id: 'CEV-MIAA-006',
      type: 'FIRST_CHARGEBACK',
      payment_id: 'PAY-MIAA-CHK-004',
      dispute_id: 'DSP-MIAA-004',
      scheme: 'Mastercard',
      last4: '5555',
      currency: 'USD',
      amount: '260.00',
      status: 'FIRST_CHARGEBACK',
      reason_code: '10.4',
      occurred_at: '2026-09-16T11:20:00Z',
      remark: '1st chargeback — other fraud',
      raw_type: 'notification_of_chargeback',
      provider: 'mastercard'
    },
    {
      id: 'CEV-MIAA-009',
      type: 'PRESENTMENT',
      payment_id: 'PAY-MIAA-CHK-004',
      dispute_id: 'DSP-MIAA-004',
      scheme: 'Mastercard',
      last4: '5555',
      currency: 'USD',
      amount: '260.00',
      status: 'PRESENTMENT',
      occurred_at: '2026-09-15T09:45:00Z',
      remark: 'Presentment for checkout PAY-MIAA-CHK-004',
      raw_type: 'first.presentment',
      provider: 'mastercard'
    },
    {
      id: 'CEV-MIAA-017',
      type: 'ARBITRATION',
      payment_id: 'PAY-MIAA-CHK-005',
      dispute_id: 'DSP-MIAA-005',
      scheme: 'Mastercard',
      last4: '5555',
      currency: 'USD',
      amount: '310.00',
      status: 'ARBITRATION',
      reason_code: '10.4',
      occurred_at: '2026-09-19T12:30:00Z',
      remark: 'Card scheme arbitration outcome',
      raw_type: 'arbitration.opened',
      provider: 'mastercard'
    },
    {
      id: 'CEV-MIAA-016B',
      type: 'SECOND_CHARGEBACK',
      payment_id: 'PAY-MIAA-CHK-005',
      dispute_id: 'DSP-MIAA-005',
      scheme: 'Mastercard',
      last4: '5555',
      currency: 'USD',
      amount: '310.00',
      status: 'SECOND_CHARGEBACK',
      reason_code: '10.4',
      occurred_at: '2026-09-18T16:00:00Z',
      remark: 'Issuer returned a 2nd chargeback',
      raw_type: 'pre_arbitration',
      provider: 'mastercard'
    },
    {
      id: 'CEV-MIAA-016',
      type: 'REPRESENTMENT',
      payment_id: 'PAY-MIAA-CHK-005',
      dispute_id: 'DSP-MIAA-005',
      scheme: 'Mastercard',
      last4: '5555',
      currency: 'USD',
      amount: '310.00',
      status: 'REPRESENTMENT',
      reason_code: '10.4',
      occurred_at: '2026-09-16T14:00:00Z',
      remark: 'Merchant represented with delivery proof',
      raw_type: 'second.presentment',
      provider: 'mastercard'
    },
    {
      id: 'CEV-MIAA-015',
      type: 'FIRST_CHARGEBACK',
      payment_id: 'PAY-MIAA-CHK-005',
      dispute_id: 'DSP-MIAA-005',
      scheme: 'Mastercard',
      last4: '5555',
      currency: 'USD',
      amount: '310.00',
      status: 'FIRST_CHARGEBACK',
      reason_code: '10.4',
      occurred_at: '2026-09-15T11:00:00Z',
      remark: '1st chargeback — other fraud',
      raw_type: 'notification_of_chargeback',
      provider: 'mastercard'
    },
    {
      id: 'CEV-MIAA-014',
      type: 'PRESENTMENT',
      payment_id: 'PAY-MIAA-CHK-005',
      dispute_id: 'DSP-MIAA-005',
      scheme: 'Mastercard',
      last4: '5555',
      currency: 'USD',
      amount: '310.00',
      status: 'PRESENTMENT',
      occurred_at: '2026-09-14T10:00:00Z',
      remark: 'Presentment for checkout PAY-MIAA-CHK-005',
      raw_type: 'first.presentment',
      provider: 'mastercard'
    },
    {
      id: 'CEV-MIAA-005',
      type: 'FIRST_CHARGEBACK',
      payment_id: 'PAY-MIAA-CHK-003',
      dispute_id: 'DSP-MIAA-003',
      scheme: 'Visa',
      last4: '4242',
      currency: 'USD',
      amount: '220.00',
      status: 'FIRST_CHARGEBACK',
      reason_code: '13.1',
      occurred_at: '2026-09-17T15:40:00Z',
      remark: '1st chargeback — merchandise not received',
      raw_type: 'charge.dispute.created',
      provider: 'stripe'
    },
    {
      id: 'CEV-MIAA-008',
      type: 'PRESENTMENT',
      payment_id: 'PAY-MIAA-CHK-003',
      dispute_id: 'DSP-MIAA-003',
      scheme: 'Visa',
      last4: '4242',
      currency: 'USD',
      amount: '220.00',
      status: 'PRESENTMENT',
      occurred_at: '2026-09-16T12:00:00Z',
      remark: 'Presentment for checkout PAY-MIAA-CHK-003',
      raw_type: 'first.presentment',
      provider: 'checkout.com'
    },
    {
      id: 'CEV-MIAA-007',
      type: 'RFI',
      payment_id: 'PAY-MIAA-CHK-003',
      dispute_id: 'DSP-MIAA-003',
      scheme: 'Visa',
      last4: '4242',
      currency: 'USD',
      amount: '220.00',
      status: 'RFI',
      reason_code: '13.1',
      occurred_at: '2026-09-15T09:30:00Z',
      remark: 'Request for information before chargeback',
      raw_type: 'request_for_information',
      provider: 'stripe'
    },
    {
      id: 'CEV-MIAA-004',
      type: 'REFUND_SUCCEEDED',
      payment_id: 'PAY-MIAA-CHK-002',
      refund_id: 'RFD-MIAA-002',
      refund_kind: 'WITH_GOODS',
      scheme: 'Mastercard',
      last4: '5555',
      currency: 'USD',
      amount: '150.00',
      status: 'REFUND_SUCCEEDED',
      occurred_at: '2026-09-16T09:15:00Z',
      remark: 'Partial refund with goods return',
      ledger_effects: [{ bucket: 'available', direction: 'DEBIT', amount: '150.00' }]
    },
    {
      id: 'CEV-MIAA-003',
      type: 'REFUND_SUCCEEDED',
      payment_id: 'PAY-MIAA-CHK-001',
      refund_id: 'RFD-MIAA-001',
      refund_kind: 'MONEY_ONLY',
      scheme: 'Visa',
      last4: '4242',
      currency: 'USD',
      amount: '320.00',
      status: 'REFUND_SUCCEEDED',
      occurred_at: '2026-09-15T13:05:00Z',
      remark: 'Partial money-only refund',
      ledger_effects: [{ bucket: 'available', direction: 'DEBIT', amount: '320.00' }]
    },
    {
      id: 'CEV-MIAA-002',
      type: 'CAPTURED',
      payment_id: 'PAY-MIAA-CHK-002',
      scheme: 'Mastercard',
      last4: '5555',
      currency: 'USD',
      amount: '1800.00',
      status: 'CAPTURED',
      occurred_at: '2026-09-14T10:30:00Z',
      remark: 'Hosted checkout captured',
      raw_type: 'payment_captured',
      provider: 'checkout.com',
      ledger_effects: [{ bucket: 'available', direction: 'CREDIT', amount: '1800.00' }]
    },
    {
      id: 'CEV-MIAA-001',
      type: 'CAPTURED',
      payment_id: 'PAY-MIAA-CHK-001',
      scheme: 'Visa',
      last4: '4242',
      currency: 'USD',
      amount: '2500.00',
      status: 'CAPTURED',
      occurred_at: '2026-09-13T08:20:00Z',
      remark: 'Hosted checkout captured',
      raw_type: 'payment_captured',
      provider: 'checkout.com',
      ledger_effects: [{ bucket: 'available', direction: 'CREDIT', amount: '2500.00' }]
    }
  ]
}

function lilyCardTxns() {
  return [
    {
      id: 'CEV-LILY-016',
      type: 'FIRST_CHARGEBACK',
      payment_id: 'PAY-LILY-CHK-002',
      dispute_id: 'DSP-LILY-002',
      scheme: 'Visa',
      last4: '4242',
      currency: 'USD',
      amount: '350.00',
      status: 'FIRST_CHARGEBACK',
      reason_code: '13.1',
      occurred_at: '2026-09-16T04:10:00Z',
      remark: '1st chargeback — merchandise not received',
      raw_type: 'charge.dispute.created',
      provider: 'stripe',
      ledger_effects: [
        { bucket: 'available', direction: 'DEBIT', amount: '350.00' },
        { bucket: 'dispute_hold', direction: 'CREDIT', amount: '350.00' }
      ]
    },
    {
      id: 'CEV-LILY-018',
      type: 'PRESENTMENT',
      payment_id: 'PAY-LILY-CHK-002',
      dispute_id: 'DSP-LILY-002',
      scheme: 'Visa',
      last4: '4242',
      currency: 'USD',
      amount: '350.00',
      status: 'PRESENTMENT',
      occurred_at: '2026-09-13T16:30:00Z',
      remark: 'Presentment to the issuer for checkout PAY-LILY-CHK-002',
      raw_type: 'first.presentment',
      provider: 'checkout.com'
    },
    {
      id: 'CEV-LILY-026',
      type: 'ARBITRATION',
      payment_id: 'PAY-LILY-CHK-005',
      dispute_id: 'DSP-LILY-005',
      scheme: 'Mastercard',
      last4: '4444',
      currency: 'USD',
      amount: '480.00',
      status: 'ARBITRATION',
      reason_code: '10.4',
      occurred_at: '2026-09-14T15:30:00Z',
      remark: 'Merchant still disputed — card scheme arbitration opened',
      raw_type: 'arbitration.opened',
      provider: 'mastercard'
    },
    {
      id: 'CEV-LILY-025',
      type: 'SECOND_CHARGEBACK',
      payment_id: 'PAY-LILY-CHK-005',
      dispute_id: 'DSP-LILY-005',
      scheme: 'Mastercard',
      last4: '4444',
      currency: 'USD',
      amount: '480.00',
      status: 'SECOND_CHARGEBACK',
      reason_code: '10.4',
      occurred_at: '2026-09-12T10:00:00Z',
      remark: 'Issuer returned a 2nd chargeback after representment',
      raw_type: 'pre_arbitration',
      provider: 'mastercard'
    },
    {
      id: 'CEV-LILY-024',
      type: 'REPRESENTMENT',
      payment_id: 'PAY-LILY-CHK-005',
      dispute_id: 'DSP-LILY-005',
      scheme: 'Mastercard',
      last4: '4444',
      currency: 'USD',
      amount: '480.00',
      status: 'REPRESENTMENT',
      reason_code: '10.4',
      occurred_at: '2026-09-10T14:20:00Z',
      remark: 'Merchant represented with shipping evidence',
      raw_type: 'second.presentment',
      provider: 'mastercard'
    },
    {
      id: 'CEV-LILY-023',
      type: 'FIRST_CHARGEBACK',
      payment_id: 'PAY-LILY-CHK-005',
      dispute_id: 'DSP-LILY-005',
      scheme: 'Mastercard',
      last4: '4444',
      currency: 'USD',
      amount: '480.00',
      status: 'FIRST_CHARGEBACK',
      reason_code: '10.4',
      occurred_at: '2026-09-09T11:00:00Z',
      remark: '1st chargeback — other fraud',
      raw_type: 'notification_of_chargeback',
      provider: 'mastercard',
      ledger_effects: [
        { bucket: 'available', direction: 'DEBIT', amount: '480.00' },
        { bucket: 'dispute_hold', direction: 'CREDIT', amount: '480.00' }
      ]
    },
    {
      id: 'CEV-LILY-022',
      type: 'PRESENTMENT',
      payment_id: 'PAY-LILY-CHK-005',
      dispute_id: 'DSP-LILY-005',
      scheme: 'Mastercard',
      last4: '4444',
      currency: 'USD',
      amount: '480.00',
      status: 'PRESENTMENT',
      occurred_at: '2026-09-08T09:45:00Z',
      remark: 'Presentment to the issuer for checkout PAY-LILY-CHK-005',
      raw_type: 'first.presentment',
      provider: 'mastercard'
    },
    {
      id: 'CEV-LILY-021',
      type: 'CAPTURED',
      payment_id: 'PAY-LILY-CHK-005',
      scheme: 'Mastercard',
      last4: '4444',
      currency: 'USD',
      amount: '480.00',
      status: 'CAPTURED',
      occurred_at: '2026-09-08T09:30:00Z',
      remark: 'Hosted checkout captured',
      raw_type: 'payment_captured',
      provider: 'checkout.com',
      ledger_effects: [
        { bucket: 'reserved', direction: 'DEBIT', amount: '480.00' },
        { bucket: 'available', direction: 'CREDIT', amount: '480.00' }
      ]
    },
    {
      id: 'CEV-LILY-020',
      type: 'AUTHORIZED',
      payment_id: 'PAY-LILY-CHK-005',
      scheme: 'Mastercard',
      last4: '4444',
      currency: 'USD',
      amount: '480.00',
      status: 'AUTHORIZED',
      occurred_at: '2026-09-08T09:01:00Z',
      remark: 'Authorization hold',
      ledger_effects: [{ bucket: 'reserved', direction: 'CREDIT', amount: '480.00' }]
    },
    {
      id: 'CEV-LILY-019',
      type: 'CHECKOUT_CREATED',
      payment_id: 'PAY-LILY-CHK-005',
      scheme: 'Mastercard',
      last4: '4444',
      currency: 'USD',
      amount: '480.00',
      status: 'CHECKOUT_CREATED',
      occurred_at: '2026-09-08T09:00:00Z',
      remark: 'Hosted checkout created'
    },
    {
      id: 'CEV-LILY-015',
      type: 'REFUND_PENDING',
      payment_id: 'PAY-LILY-CHK-002',
      refund_id: 'RFD-LILY-002B',
      refund_kind: 'WITH_GOODS',
      scheme: 'Visa',
      last4: '4242',
      currency: 'USD',
      amount: '80.00',
      status: 'REFUND_PENDING',
      occurred_at: '2026-09-16T01:20:00Z',
      remark: 'Partial refund with goods return on checkout PAY-LILY-CHK-002'
    },
    {
      id: 'CEV-LILY-014',
      type: 'CHECKOUT_CREATED',
      payment_id: 'PAY-LILY-CHK-003',
      scheme: 'Visa',
      last4: '4242',
      currency: 'USD',
      amount: '420.00',
      status: 'CHECKOUT_CREATED',
      occurred_at: '2026-09-15T18:40:00Z',
      remark: 'Hosted checkout started — not captured yet',
      raw_type: 'payment_created',
      provider: 'checkout.com'
    },
    {
      id: 'CEV-LILY-011',
      type: 'REFUND_SUCCEEDED',
      payment_id: 'PAY-LILY-CHK-002',
      refund_id: 'RFD-LILY-002A',
      refund_kind: 'MONEY_ONLY',
      scheme: 'Visa',
      last4: '4242',
      currency: 'USD',
      amount: '200.00',
      status: 'REFUND_SUCCEEDED',
      occurred_at: '2026-09-14T08:22:00Z',
      remark: 'Partial money-only refund posted',
      ledger_effects: [{ bucket: 'available', direction: 'DEBIT', amount: '200.00' }]
    },
    {
      id: 'CEV-LILY-010',
      type: 'CAPTURED',
      payment_id: 'PAY-LILY-CHK-002',
      scheme: 'Visa',
      last4: '4242',
      currency: 'USD',
      amount: '1800.00',
      status: 'CAPTURED',
      occurred_at: '2026-09-13T16:12:00Z',
      remark: 'Hosted checkout captured',
      raw_type: 'payment_captured',
      provider: 'checkout.com',
      ledger_effects: [
        { bucket: 'reserved', direction: 'DEBIT', amount: '1800.00' },
        { bucket: 'available', direction: 'CREDIT', amount: '1800.00' }
      ]
    },
    {
      id: 'CEV-LILY-009',
      type: 'AUTHORIZED',
      payment_id: 'PAY-LILY-CHK-002',
      scheme: 'Visa',
      last4: '4242',
      currency: 'USD',
      amount: '1800.00',
      status: 'AUTHORIZED',
      occurred_at: '2026-09-13T16:11:00Z',
      remark: 'Authorization hold',
      ledger_effects: [{ bucket: 'reserved', direction: 'CREDIT', amount: '1800.00' }]
    },
    {
      id: 'CEV-LILY-008',
      type: 'CHECKOUT_CREATED',
      payment_id: 'PAY-LILY-CHK-002',
      scheme: 'Visa',
      last4: '4242',
      currency: 'USD',
      amount: '1800.00',
      status: 'CHECKOUT_CREATED',
      occurred_at: '2026-09-13T16:10:00Z',
      remark: 'Hosted checkout created'
    },
    {
      id: 'CEV-LILY-007',
      type: 'DECLINED',
      payment_id: 'PAY-LILY-CHK-004',
      scheme: 'Mastercard',
      last4: '4444',
      currency: 'USD',
      amount: '95.00',
      status: 'DECLINED',
      occurred_at: '2026-09-13T12:40:00Z',
      remark: 'Issuer declined — insufficient funds'
    },
    {
      id: 'CEV-LILY-006',
      type: 'CAPTURED',
      payment_id: 'PAY-LILY-CHK-001',
      scheme: 'Visa',
      last4: '4242',
      currency: 'USD',
      amount: '5000.00',
      status: 'CAPTURED',
      occurred_at: '2026-09-13T09:30:00Z',
      remark: 'Hosted checkout captured into card balance',
      raw_type: 'payment_captured',
      provider: 'checkout.com',
      ledger_effects: [
        { bucket: 'reserved', direction: 'DEBIT', amount: '5000.00' },
        { bucket: 'available', direction: 'CREDIT', amount: '5000.00' }
      ]
    },
    {
      id: 'CEV-LILY-005',
      type: 'AUTHORIZED',
      payment_id: 'PAY-LILY-CHK-001',
      scheme: 'Visa',
      last4: '4242',
      currency: 'USD',
      amount: '5000.00',
      status: 'AUTHORIZED',
      occurred_at: '2026-09-13T09:01:00Z',
      remark: 'Authorization hold',
      raw_type: 'payment_authorized',
      provider: 'checkout.com',
      ledger_effects: [{ bucket: 'reserved', direction: 'CREDIT', amount: '5000.00' }]
    },
    {
      id: 'CEV-LILY-004',
      type: 'CHECKOUT_CREATED',
      payment_id: 'PAY-LILY-CHK-001',
      scheme: 'Visa',
      last4: '4242',
      currency: 'USD',
      amount: '5000.00',
      status: 'CHECKOUT_CREATED',
      occurred_at: '2026-09-13T09:00:00Z',
      remark: 'Hosted checkout created',
      raw_type: 'payment_created',
      provider: 'checkout.com'
    }
  ]
}
