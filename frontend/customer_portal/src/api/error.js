import axios from 'axios'

const codeMessages = {
  MERCHANT_PENDING: 'Customer due diligence and product admission remain pending',
  MERCHANT_SUSPENDED: 'The customer is suspended from transacting',
  LICENSE_EXPIRED: 'The business licence has expired',
  KYC_NOT_APPROVED: 'Customer due diligence has not been approved',
  PRODUCT_NOT_ENABLED: 'The remittance product has not been enabled',
  FEE_NOT_CONFIGURED: 'A valid remittance tariff has not been configured',
  FX_RATE_UNAVAILABLE: 'The applicable exchange rate is presently unavailable',
  QUOTE_EXPIRED: 'The quotation has expired; generate a new quotation',
  PERMISSION_DENIED: 'The authenticated principal is not authorised for this operation',
  INVALID_CURRENCY: 'The currency is not a supported ISO 4217 code',
  MERCHANT_NOT_BOUND: 'No customer entity is linked to this account. Contact operations.'
}

function flatten(value, path = '', output = []) {
  if (Array.isArray(value)) {
    value.forEach((item) => flatten(item, path, output))
  } else if (value && typeof value === 'object') {
    Object.entries(value).forEach(([key, item]) => {
      flatten(item, path ? `${path}.${key}` : key, output)
    })
  } else if (value != null && value !== '') {
    output.push(path ? `${path}: ${String(value)}` : String(value))
  }
  return output
}

export function extractErrorMessage(data, fallback = '') {
  const defaultMessage = fallback || 'The request could not be completed'
  if (!data) return defaultMessage
  if (typeof data === 'string') return data
  const localized = codeMessages[data.code]
  if (localized) return localized
  if (data.message) return String(data.message)
  if (typeof data.detail === 'string') return data.detail
  if (data.error) return String(data.error)
  const fieldErrors = flatten(data.details?.fields || data.fields || data.detail)
  return fieldErrors.length ? fieldErrors.slice(0, 3).join('; ') : defaultMessage
}

export async function parseResponseData(data) {
  if (!(data instanceof Blob)) return data
  const text = await data.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export function describeTransportError(error) {
  if (axios.isCancel(error)) return null
  if (error.code === 'ECONNABORTED') {
    return 'The request timed out'
  }
  if (!error.response) {
    return navigator.onLine
      ? 'The server could not be reached'
      : 'The network connection is unavailable'
  }
  return ''
}
