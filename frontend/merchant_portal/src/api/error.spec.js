import { describe, expect, it } from 'vitest'
import { extractErrorMessage, describeTransportError } from './error'

describe('API error formatting', () => {
  it('localizes stable remittance error codes', () => {
    expect(extractErrorMessage({ code: 'QUOTE_EXPIRED', message: 'ignored' }))
      .toContain('expired')
  })

  it('recursively displays nested field errors', () => {
    expect(extractErrorMessage({
      code: 'VALIDATION_ERROR',
      details: { fields: { beneficiary: { bank: ['required'] } } }
    })).toBe('beneficiary.bank: required')
  })

  it('distinguishes offline transport failures', () => {
    Object.defineProperty(window.navigator, 'onLine', {
      configurable: true,
      value: false
    })
    expect(describeTransportError({ response: null })).toContain('unavailable')
  })
})
