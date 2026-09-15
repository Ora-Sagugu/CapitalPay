import request from './request'

export function getCoopBanks(params) {
  return request.get('/v1/admin/coop-banks/', { params })
}
export function createCoopBank(data) {
  return request.post('/v1/admin/coop-banks/', data)
}
export function updateCoopBank(id, data) {
  return request.put(`/v1/admin/coop-banks/${id}/`, data)
}
export function deleteCoopBank(id) {
  return request.delete(`/v1/admin/coop-banks/${id}/`)
}
export function getFeeModels(params) {
  return request.get('/v1/admin/fee-models/', { params })
}
export function createFeeModel(data) {
  return request.post('/v1/admin/fee-models/', data)
}
export function updateFeeModel(id, data) {
  return request.put(`/v1/admin/fee-models/${id}/`, data)
}
export function deleteFeeModel(id) {
  return request.delete(`/v1/admin/fee-models/${id}/`)
}
export function getBankFeeConfigs(params) {
  return request.get('/v1/admin/bank-fee-configs/', { params })
}
export function createBankFeeConfig(data) {
  return request.post('/v1/admin/bank-fee-configs/', data)
}
export function updateBankFeeConfig(id, data) {
  return request.put(`/v1/admin/bank-fee-configs/${id}/`, data)
}
export function deleteBankFeeConfig(id) {
  return request.delete(`/v1/admin/bank-fee-configs/${id}/`)
}
export function getRiskRatingLimits() {
  return request.get('/v1/admin/risk-rating-limits/')
}
export function updateRiskRatingLimit(id, data) {
  return request.patch(`/v1/admin/risk-rating-limits/${id}/`, data)
}
export function getRemittanceFeeConfig() {
  return request.get('/v1/admin/remittance-fee-config/')
}
export function updateRemittanceFeeConfig(data) {
  return request.put('/v1/admin/remittance-fee-config/', data)
}
