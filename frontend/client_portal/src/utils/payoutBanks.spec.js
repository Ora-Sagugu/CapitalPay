import { describe, expect, it } from 'vitest'

import {
  confirmTransferPayload,
  isPayoutBankDisabled,
  payoutSelectionComplete,
  recommendedPayoutCodes,
  splitPayoutLegs
} from './payoutBanks'

const banks = [
  { bank_code: 'CHEAP', balance: '20.00', sufficient: false, partial: true, selectable: true },
  { bank_code: 'MID', balance: '500.00', sufficient: true, partial: false, selectable: true },
  { bank_code: 'DEAR', balance: '5000.00', sufficient: true, partial: false, selectable: true }
]

describe('payout bank split selection', () => {
  it('recommends the leftover split when the cheapest bank is short', () => {
    expect(recommendedPayoutCodes({
      recommended_bank_code: 'CHEAP',
      recommended_bank_codes: ['CHEAP', 'MID']
    })).toEqual(['CHEAP', 'MID'])
  })

  it('splits 100 into remaining 20 plus 80 on the second bank', () => {
    const legs = splitPayoutLegs(banks, ['CHEAP', 'MID'], '100.00')
    expect(legs.map((leg) => [leg.bank_code, leg.payout_amount])).toEqual([
      ['CHEAP', 20],
      ['MID', 80]
    ])
    expect(payoutSelectionComplete(banks, ['CHEAP', 'MID'], '100.00')).toBe(true)
    expect(confirmTransferPayload(['CHEAP', 'MID'])).toEqual({
      bank_codes: ['CHEAP', 'MID']
    })
  })

  it('does not split two banks that each cover the payout', () => {
    expect(splitPayoutLegs(banks, ['MID', 'DEAR'], '100.00')).toEqual([])
    expect(payoutSelectionComplete(banks, ['MID', 'DEAR'], '100.00')).toBe(false)
    expect(isPayoutBankDisabled(banks[2], banks, ['MID'], '100.00')).toBe(true)
  })

  it('keeps a sufficient bank selectable on its own', () => {
    expect(payoutSelectionComplete(banks, ['MID'], '100.00')).toBe(true)
    expect(confirmTransferPayload(['MID'])).toEqual({ bank_code: 'MID' })
    expect(isPayoutBankDisabled(banks[0], banks, [], '100.00')).toBe(false)
  })
})
