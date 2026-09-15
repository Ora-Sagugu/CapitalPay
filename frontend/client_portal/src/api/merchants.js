import request from './request'

export function getMerchants(params) {
  return request.get('/v1/admin/merchants/', { params })
}
export function getRemittanceMerchantOptions(params) {
  return request.get('/v1/admin/merchants/remittance-options/', { params })
}
export function getMerchant(merchantNo) {
  return request.get(`/v1/admin/merchants/${merchantNo}/`)
}
export function updateMerchant(merchantNo, data) {
  return request.patch(`/v1/admin/merchants/${merchantNo}/`, data)
}
export function getMerchantStats() {
  return request.get('/v1/admin/merchants/stats/')
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
export function setMerchantKyc(merchantNo, data) {
  return request.put(`/v1/admin/merchants/${merchantNo}/kyc/`, data)
}
export function getMerchantFees(merchantNo) {
  return request.get(`/v1/admin/merchants/${merchantNo}/fees/`)
}
export function setMerchantFee(merchantNo, data) {
  return request.post(`/v1/admin/merchants/${merchantNo}/fees/`, data)
}
export function getSettlementAccounts(merchantNo) {
  return request.get(`/v1/admin/merchants/${merchantNo}/settlement-accounts/`)
}
export function setSettlementAccount(merchantNo, data) {
  return request.post(`/v1/admin/merchants/${merchantNo}/settlement-accounts/`, data)
}
export function getPaymentProducts(merchantNo) {
  return request.get(`/v1/admin/merchants/${merchantNo}/payment-products/`)
}
export function setPaymentProduct(merchantNo, data) {
  return request.put(`/v1/admin/merchants/${merchantNo}/payment-products/`, data)
}
export function getSplitConfig(merchantNo) {
  return request.get(`/v1/admin/merchants/${merchantNo}/split-config/`)
}
export function saveSplitConfig(merchantNo, data) {
  return request.put(`/v1/admin/merchants/${merchantNo}/split-config/`, data)
}
export function getPendingFunds(merchantNo) {
  return request.get(`/v1/admin/merchants/${merchantNo}/pending-funds/`)
}
export function getSettledFunds(merchantNo) {
  return request.get(`/v1/admin/merchants/${merchantNo}/settled-funds/`)
}
export function getPendingOrders(merchantNo) {
  return request.get(`/v1/admin/merchants/${merchantNo}/pending-orders/`)
}
export function getSettledOrders(merchantNo) {
  return request.get(`/v1/admin/merchants/${merchantNo}/settled-orders/`)
}
export function exportSettledFunds(merchantNo) {
  return request.get(`/v1/admin/merchants/${merchantNo}/settled-funds-export/`, { responseType: 'blob' })
}
export function exportSettledOrders(merchantNo) {
  return request.get(`/v1/admin/merchants/${merchantNo}/settled-orders-export/`, { responseType: 'blob' })
}
