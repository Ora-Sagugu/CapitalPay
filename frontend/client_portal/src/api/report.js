import request from './request'

export function queryReport(path, params) {
  return request.post(`/v1/admin/reports/${path}/query/`, params)
}
export function exportReport(path, params) {
  return request.post(`/v1/admin/reports/${path}/export/`, params, { responseType: 'blob' })
}
export function generateReport(path, params) {
  return request.post(`/v1/admin/reports/${path}/generate/`, params)
}

export const reportPaths = {
  remittance: 'remittance',
  merchantDaily: 'merchant-daily',
  channelFee: 'channel-fee',
  platformSummary: 'platform-summary',
  settleBatches: 'settle-batches',
  settleDetails: 'settle-details'
}

function analyticsParams(filters) {
  const [date_from, date_to] = filters.range || []
  return {
    date_from,
    date_to,
    time_basis: filters.time_basis || 'created_at',
    merchant_id: filters.merchant_id || undefined,
    agent_id: filters.agent_id || undefined,
    user_id: filters.user_id || undefined,
    bank_code: filters.bank_code || undefined,
    from_currency: filters.from_currency || undefined,
    to_currency: filters.to_currency || undefined,
    status: filters.status || undefined,
    order_no: filters.order_no || undefined,
    unique_identification_no: filters.uin || undefined,
    prn_code: filters.prn_code || undefined,
    dimension: filters.dimension || undefined,
    page: filters.page || undefined,
    page_size: filters.page_size || undefined
  }
}

export function getAnalyticsSummary(filters) {
  return request.get('/v1/admin/reports/analytics/summary/', { params: analyticsParams(filters) })
}
export function getAnalyticsTrend(filters) {
  return request.get('/v1/admin/reports/analytics/trend/', { params: analyticsParams(filters) })
}
export function getAnalyticsBreakdowns(filters) {
  return request.get('/v1/admin/reports/analytics/breakdowns/', { params: analyticsParams(filters) })
}
export function getAnalyticsTransactions(filters) {
  return request.get('/v1/admin/reports/analytics/transactions/', { params: analyticsParams(filters) })
}
export function getAnalyticsTrace(orderNo) {
  return request.get('/v1/admin/reports/analytics/trace/', { params: { order_no: orderNo } })
}
export function exportAnalytics(filters) {
  return request.post('/v1/admin/reports/analytics/export/', analyticsParams(filters), { responseType: 'blob' })
}
