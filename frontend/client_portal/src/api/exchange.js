import request from './request'

export function getExchangeRates(params) {
  return request.get('/v1/admin/exchange-rates/', { params })
}
export function createExchangeRate(data) {
  return request.post('/v1/admin/exchange-rates/', data)
}
export function updateExchangeRate(id, data) {
  return request.patch(`/v1/admin/exchange-rates/${id}/`, data)
}
export function getLatestRate(params) {
  return request.get('/v1/admin/exchange-rates/latest/', { params })
}
export function batchUpdateRates(data) {
  return request.post('/v1/admin/exchange-rates/batch-update/', data)
}
export function importDailyRates(data = {}) {
  return request.post('/v1/admin/exchange-rates/import_daily/', data)
}
export function syncRealtimeRates(data) {
  return request.post('/v1/admin/exchange-rates/sync_realtime/', data)
}
export function importCsvRates(formData) {
  return request.post('/v1/admin/exchange-rates/import-csv/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
export function convertRate(data) {
  return request.post('/v1/admin/exchange-rates/convert/', data)
}
export function getExchangeStats() {
  return request.get('/v1/admin/exchange-rates/stats/')
}
