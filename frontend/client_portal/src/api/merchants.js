import request from './request'

export function getMerchants(params) {
  return request.get('/v1/admin/merchants/', { params })
}
export function getMerchant(merchantNo) {
  return request.get(`/v1/admin/merchants/${merchantNo}/`)
}
export function updateMerchant(merchantNo, data) {
  return request.patch(`/v1/admin/merchants/${merchantNo}/`, data)
}
export function getMerchantKyc(merchantNo) {
  return request.get(`/v1/admin/merchants/${merchantNo}/kyc/`)
}
export function reviewMerchantKyc(merchantNo, data) {
  return request.post(`/v1/admin/merchants/${merchantNo}/review-kyc/`, data)
}
export function updateRiskLevel(merchantNo, data) {
  return request.post(`/v1/admin/merchants/${merchantNo}/update-risk-level/`, data)
}
