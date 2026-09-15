import { describe, expect, it } from 'vitest'
import { extractErrorMessage, describeTransportError } from './error'

describe('API error formatting', () => {
  it('localizes stable remittance error codes', () => {
    expect(extractErrorMessage({ code: 'MERCHANT_PENDING', message: 'ignored' }))
      .toContain('due diligence')
  })

  it('recursively displays nested field errors', () => {
    expect(extractErrorMessage({
      code: 'VALIDATION_ERROR',
      details: { fields: { beneficiary: { account: ['required'] } } }
    })).toBe('beneficiary.account: required')
  })

  it('distinguishes timeout from API failures', () => {
    expect(describeTransportError({ code: 'ECONNABORTED' })).toContain('timed out')
  })
})
